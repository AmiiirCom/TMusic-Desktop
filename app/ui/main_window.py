import logging
from pathlib import Path
import shutil
from PySide6.QtCore import Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from app.cache.service import CacheManager
from app.config import AppConfig
from app.models.chat import OwnedChat
from app.models.track import Track
from app.network.meter import NetworkMeter
from app.network.stream_server import LocalStreamServer
from app.player.service import PlayerService
from app.platform.tray_service import TrayService
from app.settings.service import ProxySettings, SettingsService
from app.telegram.adapter import TDLibAdapter
from app.telegram.enums import AuthState
from app.telegram.service import TelegramService
from app.ui.views.login_view import LoginView
from app.ui.views.lyrics_dialog import LyricsDialog
from app.ui.views.main_view import MainView
from app.ui.views.proxy_dialog import ProxyDialog
from app.ui.views.settings_dialog import SettingsDialog
from app.ui.views.track_info_dialog import TrackInfoDialog

logger = logging.getLogger("tmusic.main_window")


def has_saved_telegram_session(config: AppConfig) -> bool:
    td_binlog = config.tdlib_dir / "td.binlog"
    return td_binlog.exists() and td_binlog.stat().st_size > 0


class MainWindow(QMainWindow):
    """Root main window coordinating views, dialogs, tray service, and background services."""

    def __init__(
        self,
        config: AppConfig,
        telegram_service: TelegramService,
        player_service: PlayerService,
        cache_manager: CacheManager,
        network_meter: NetworkMeter,
        settings_service: SettingsService,
        stream_server: LocalStreamServer,
        tdlib_adapter: TDLibAdapter,
    ) -> None:
        super().__init__()
        self._config = config
        self._telegram = telegram_service
        self._player = player_service
        self._cache = cache_manager
        self._meter = network_meter
        self._settings = settings_service
        self._stream_server = stream_server
        self._tdlib_adapter = tdlib_adapter
        self._is_quitting = False

        self.setWindowTitle(f"{config.app_name} Desktop")
        self.resize(1100, 750)

        self._central_stack = QStackedWidget(self)
        self.setCentralWidget(self._central_stack)

        self._main_view = MainView(self._config, self)
        self._login_view = LoginView(self)

        self._central_stack.addWidget(self._main_view)
        self._central_stack.addWidget(self._login_view)

        if has_saved_telegram_session(self._config):
            self._central_stack.setCurrentWidget(self._main_view)
        else:
            self._central_stack.setCurrentWidget(self._login_view)

        self._connect_signals()
        self._restore_preferences()

        self._tray = TrayService(self, self._player, self._config)
        self._tray.show_window_requested.connect(self._restore_window)
        self._tray.quit_requested.connect(self._quit_application)

        self._telegram.load_cached_state()
        self._apply_saved_proxy()

    def _connect_signals(self) -> None:
        # MainView events
        self._main_view.chat_selected.connect(self._on_chat_selected)
        self._main_view.track_selected.connect(self._on_track_selected)
        self._main_view.track_like_toggled.connect(self._telegram.toggle_track_like)
        self._main_view.load_more_tracks_requested.connect(self._telegram.load_more_tracks)
        self._main_view.settings_requested.connect(self._open_settings_dialog)
        self._main_view.search_full_requested.connect(self._telegram.search_tracks)
        self._main_view.chat_search_requested.connect(self._telegram.search_chats)

        # LoginView events
        self._login_view.phone_submitted.connect(self._telegram.send_phone_number)
        self._login_view.code_submitted.connect(self._telegram.send_code)
        self._login_view.password_submitted.connect(self._telegram.send_password)
        self._login_view.proxy_configured.connect(self._on_proxy_configured)

        # PlayerBar events
        pb = self._main_view.player_bar
        pb.play_pause_clicked.connect(self._player.toggle_play_pause)
        pb.next_clicked.connect(self._player.play_next)
        pb.previous_clicked.connect(self._player.play_previous)
        pb.seek_requested.connect(self._player.seek)
        pb.volume_changed.connect(self._on_volume_changed)
        pb.speed_changed.connect(self._on_speed_changed)
        pb.lyrics_clicked.connect(self._open_lyrics_dialog)
        pb.track_info_clicked.connect(self._open_track_info_dialog)
        pb.track_label_clicked.connect(self._on_track_label_clicked)
        pb.like_clicked.connect(self._on_player_like_clicked)

        # PlayerService events
        self._player.track_changed.connect(pb.set_track)
        self._player.track_changed.connect(self._main_view.set_active_track)
        self._player.playback_state_changed.connect(pb.set_playback_state)
        self._player.playback_state_changed.connect(self._telegram.set_network_monitor_active)
        self._player.playback_rate_changed.connect(pb.set_playback_rate)
        self._player.position_changed.connect(pb.set_position)
        self._player.duration_changed.connect(pb.set_duration)
        self._player.metadata_updated.connect(pb.update_metadata)

        # Meter and Telegram media integration
        self._meter.stats_updated.connect(self._main_view.set_network_stats)
        self._telegram.network_traffic_received.connect(self._meter.update_network_stats)
        self._telegram.cover_downloaded.connect(self._main_view.update_track_cover)
        self._telegram.cover_downloaded.connect(self._player.update_track_cover)
        self._telegram.track_reaction_updated.connect(self._main_view.update_track_reaction)
        self._telegram.track_reaction_updated.connect(self._player.update_track_reaction)

        # Telegram service events
        self._telegram.auth_state_changed.connect(self._on_auth_state_changed)
        self._telegram.auth_error.connect(self._login_view.show_error)
        self._telegram.connection_state_changed.connect(self._on_connection_state_changed)
        self._telegram.connection_retry_interval_changed.connect(self._main_view.set_retry_interval)
        self._telegram.user_loaded.connect(self._main_view.set_user)
        self._telegram.owned_chats_loaded.connect(self._main_view.set_owned_chats)
        self._telegram.chat_search_results_received.connect(self._main_view.on_chat_search_results)
        self._telegram.tracks_loaded.connect(self._on_initial_tracks_loaded)
        self._telegram.tracks_appended.connect(self._on_tracks_appended)
        self._telegram.tracks_prepended.connect(self._on_tracks_prepended)
        self._telegram.tracks_deleted.connect(self._main_view.remove_tracks)
        self._telegram.tracks_deleted.connect(self._player.remove_from_playlist)
        self._telegram.search_results_received.connect(self._main_view.on_full_search_results)

    def _restore_preferences(self) -> None:
        saved_vol = self._settings.preferences.volume
        self._main_view.player_bar.vol_slider.setValue(saved_vol)
        self._player.set_volume(saved_vol)

        saved_speed = self._settings.preferences.playback_rate
        self._main_view.player_bar.set_playback_rate(saved_speed)
        self._player.set_playback_rate(saved_speed)

    def _apply_saved_proxy(self) -> None:
        proxy = self._settings.preferences.proxy
        self._telegram.apply_proxy_settings(proxy)
        self._main_view.set_connection_state("connectionStateConnecting", proxy)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._is_quitting:
            event.ignore()
            self.hide()
            self._telegram.set_online_status(False)
            self._telegram.set_network_monitor_active(False)
            self._tray.show_message("TMusic", "برنامه در پس‌زمینه در حال پخش است 🎵")
        else:
            event.accept()

    def _restore_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self._telegram.set_online_status(True)
        self._telegram.set_network_monitor_active(True)

    def _quit_application(self) -> None:
        self._is_quitting = True
        QApplication.quit()

    def _open_settings_dialog(self) -> None:
        dialog = SettingsDialog(self._cache, self._settings, self._config, self)
        dialog.proxy_saved.connect(self._on_proxy_configured)
        dialog.logout_requested.connect(self._on_perform_logout)
        dialog.exec()

    def _open_lyrics_dialog(self) -> None:
        track = self._player.current_track
        meta = self._player.current_metadata
        if track and meta.has_lyrics:
            dialog = LyricsDialog(title=track.display_title, artist=track.display_artist, lyrics=meta.lyrics, parent=self)
            dialog.exec()

    def _open_track_info_dialog(self) -> None:
        track = self._player.current_track
        if track:
            meta = self._player.current_metadata
            dialog = TrackInfoDialog(track=track, metadata=meta, parent=self)
            dialog.exec()

    def _on_perform_logout(self) -> None:
        self._is_quitting = True
        if self._player.is_playing:
            self._player.toggle_play_pause()

        try:
            self._telegram.stop()
            self._stream_server.stop()
            self._tdlib_adapter.close()
        except Exception as exc:
            logger.warning("Shutdown error: %s", exc)

        for dir_path in (self._config.org_data_root, self._config.org_cache_root):
            if dir_path.exists():
                try:
                    shutil.rmtree(dir_path, ignore_errors=True)
                except Exception:
                    pass

        QApplication.quit()

    @Slot(str)
    def _on_connection_state_changed(self, state: str) -> None:
        self._login_view.set_connection_status(state)
        self._main_view.set_connection_state(state, self._settings.preferences.proxy)

    @Slot(int)
    def _on_volume_changed(self, volume: int) -> None:
        self._player.set_volume(volume)
        self._settings.set_volume(volume)

    @Slot(float)
    def _on_speed_changed(self, speed: float) -> None:
        self._player.set_playback_rate(speed)
        self._settings.set_playback_rate(speed)

    @Slot(object)
    def _on_proxy_configured(self, proxy: ProxySettings) -> None:
        self._settings.set_proxy_settings(proxy)
        self._telegram.apply_proxy_settings(proxy)
        self._main_view.set_connection_state("connectionStateConnecting", proxy)

    @Slot(OwnedChat)
    def _on_chat_selected(self, chat: OwnedChat) -> None:
        self._settings.set_last_chat(chat.id)
        self._telegram.load_chat_tracks(chat.id, reset=True, chunk_size=40)

    @Slot(object, list, bool)
    def _on_initial_tracks_loaded(self, chat_id: int, tracks: list[Track], has_more: bool) -> None:
        self._main_view.set_initial_tracks(tracks, has_more=has_more)
        self._player.set_playlist(tracks)

    @Slot(object, list, bool)
    def _on_tracks_appended(self, chat_id: int, new_tracks: list[Track], has_more: bool) -> None:
        self._main_view.append_tracks(new_tracks, has_more=has_more)
        self._player.append_to_playlist(new_tracks)

    @Slot(object, list)
    def _on_tracks_prepended(self, chat_id: int, new_tracks: list[Track]) -> None:
        self._main_view.prepend_tracks(new_tracks)
        self._player.prepend_to_playlist(new_tracks)

    @Slot(Track)
    def _on_track_selected(self, track: Track) -> None:
        self._player.play_track(track)

    @Slot()
    def _on_player_like_clicked(self) -> None:
        track = self._player.current_track
        if track:
            self._telegram.toggle_track_like(track)

    @Slot(str)
    def _on_auth_state_changed(self, state: str) -> None:
        match state:
            case AuthState.WAIT_PHONE_NUMBER | AuthState.LOGGING_OUT:
                self._central_stack.setCurrentWidget(self._login_view)
                self._login_view.show_phone_step()
            case AuthState.WAIT_CODE:
                self._central_stack.setCurrentWidget(self._login_view)
                self._login_view.show_code_step()
            case AuthState.WAIT_PASSWORD:
                self._central_stack.setCurrentWidget(self._login_view)
                self._login_view.show_password_step()
            case AuthState.READY:
                self._central_stack.setCurrentWidget(self._main_view)
            case AuthState.CLOSED:
                self._on_perform_logout()

    @Slot()
    def _on_track_label_clicked(self) -> None:
        track = self._player.current_track
        if track:
            self._main_view.scroll_to_track(track)
