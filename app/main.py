import logging
from pathlib import Path
import shutil
import sys
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QStackedWidget,
)

from app.bootstrap import create_application
from app.cache.service import CacheManager
from app.config import AppConfig
from app.core.logger import setup_logging
from app.core.security import CryptoManager
from app.models.chat import OwnedChat
from app.models.track import Track
from app.models.user import TelegramUser
from app.network.meter import NetworkMeter
from app.network.stream_server import LocalStreamServer
from app.player.service import PlayerService
from app.platform.tray_service import TrayService
from app.settings.service import SettingsService
from app.telegram.adapter import TDLibAdapter
from app.telegram.enums import AuthState
from app.telegram.service import TelegramService
from app.ui.views.login_view import LoginView
from app.ui.views.lyrics_dialog import LyricsDialog
from app.ui.views.main_view import MainView
from app.ui.views.settings_dialog import SettingsDialog
from app.ui.views.track_info_dialog import TrackInfoDialog

logger = logging.getLogger("tmusic.main")


def has_saved_telegram_session(config: AppConfig) -> bool:
    td_binlog = config.tdlib_dir / "td.binlog"
    return td_binlog.exists() and td_binlog.stat().st_size > 0


class MainWindow(QMainWindow):
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

        # Main Dashboard View
        self._main_view = MainView(self._config, self)
        self._main_view.chat_selected.connect(self._on_chat_selected)
        self._main_view.track_selected.connect(self._on_track_selected)
        self._main_view.load_more_tracks_requested.connect(self._telegram.load_more_tracks)
        self._main_view.settings_requested.connect(self._open_settings_dialog)
        self._main_view.search_full_requested.connect(self._telegram.search_tracks)

        # Login View
        self._login_view = LoginView(self)
        self._login_view.phone_submitted.connect(self._telegram.send_phone_number)
        self._login_view.code_submitted.connect(self._telegram.send_code)
        self._login_view.password_submitted.connect(self._telegram.send_password)
        self._login_view.proxy_configured.connect(self._on_proxy_configured)

        self._central_stack.addWidget(self._main_view)
        self._central_stack.addWidget(self._login_view)

        if has_saved_telegram_session(self._config):
            self._central_stack.setCurrentWidget(self._main_view)
        else:
            self._central_stack.setCurrentWidget(self._login_view)

        # Connect PlayerBar UI controls with PlayerService
        player_bar = self._main_view.player_bar
        player_bar.play_pause_clicked.connect(self._player.toggle_play_pause)
        player_bar.next_clicked.connect(self._player.play_next)
        player_bar.previous_clicked.connect(self._player.play_previous)
        player_bar.seek_requested.connect(self._player.seek)
        player_bar.volume_changed.connect(self._on_volume_changed)
        player_bar.speed_changed.connect(self._on_speed_changed)
        player_bar.lyrics_clicked.connect(self._open_lyrics_dialog)
        player_bar.track_info_clicked.connect(self._open_track_info_dialog)
        player_bar.track_label_clicked.connect(self._on_track_label_clicked)

        # Restore saved settings
        saved_vol = self._settings.preferences.volume
        player_bar.vol_slider.setValue(saved_vol)
        self._player.set_volume(saved_vol)

        saved_speed = self._settings.preferences.playback_rate
        player_bar.set_playback_rate(saved_speed)
        self._player.set_playback_rate(saved_speed)

        # Player signals
        self._player.track_changed.connect(player_bar.set_track)
        self._player.track_changed.connect(self._main_view.set_active_track)
        self._player.playback_state_changed.connect(player_bar.set_playback_state)
        self._player.playback_state_changed.connect(self._telegram.set_network_monitor_active)
        self._player.playback_rate_changed.connect(player_bar.set_playback_rate)
        self._player.position_changed.connect(player_bar.set_position)
        self._player.duration_changed.connect(player_bar.set_duration)
        self._player.metadata_updated.connect(player_bar.update_metadata)

        # Network Meter & Cover Integration
        self._meter.stats_updated.connect(self._main_view.set_network_stats)
        self._telegram.network_traffic_received.connect(self._meter.update_network_stats)
        self._telegram.cover_downloaded.connect(self._main_view.update_track_cover)

        # System Tray
        self._tray = TrayService(self, self._player, self._config)
        self._tray.show_window_requested.connect(self._restore_window)
        self._tray.quit_requested.connect(self._quit_application)

        # Telegram signals
        self._telegram.auth_state_changed.connect(self._on_auth_state_changed)
        self._telegram.auth_error.connect(self._login_view.show_error)
        self._telegram.connection_state_changed.connect(self._login_view.set_connection_status)
        self._telegram.user_loaded.connect(self._main_view.set_user)
        self._telegram.owned_chats_loaded.connect(self._main_view.set_owned_chats)
        self._telegram.tracks_loaded.connect(self._on_initial_tracks_loaded)
        self._telegram.tracks_appended.connect(self._on_tracks_appended)
        self._telegram.tracks_prepended.connect(self._on_tracks_prepended)
        self._telegram.tracks_deleted.connect(self._main_view.remove_tracks)
        self._telegram.tracks_deleted.connect(self._player.remove_from_playlist)

        # Connect full search results from Telegram to MainView
        self._telegram.search_results_received.connect(self._main_view.on_full_search_results)

        self._telegram.load_cached_state()
        self._apply_saved_proxy()

    # ------------------------------------------------------------------
    # Private Methods
    # ------------------------------------------------------------------

    def _apply_saved_proxy(self) -> None:
        proxy = self._settings.preferences.proxy
        if proxy.enabled and proxy.server:
            logger.info("Applying saved proxy: %s (%s:%d)", proxy.proxy_type, proxy.server, proxy.port)
            if proxy.proxy_type == "SOCKS5":
                self._telegram.set_socks5_proxy(proxy.server, proxy.port, proxy.username, proxy.password)
            else:
                self._telegram.set_http_proxy(proxy.server, proxy.port, proxy.username, proxy.password)

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
            dialog = LyricsDialog(
                title=track.display_title,
                artist=track.display_artist,
                lyrics=meta.lyrics,
                parent=self,
            )
            dialog.exec()

    def _open_track_info_dialog(self) -> None:
        track = self._player.current_track
        if track:
            meta = self._player.current_metadata
            dialog = TrackInfoDialog(track=track, metadata=meta, parent=self)
            dialog.exec()

    def _on_perform_logout(self) -> None:
        """Complete factory reset: wipe all session data and exit immediately."""
        logger.info("Performing factory reset logout: wiping all data and cache...")
        self._is_quitting = True

        # Stop playback
        if self._player.is_playing:
            self._player.toggle_play_pause()

        # Shut down background services to release file locks
        try:
            self._telegram.stop()
            self._stream_server.stop()
            self._tdlib_adapter.close()
        except Exception as exc:
            logger.warning("Error during service shutdown: %s", exc)

        # Delete entire organization directories
        for dir_path in (self._config.org_data_root, self._config.org_cache_root):
            if dir_path.exists():
                try:
                    shutil.rmtree(dir_path, ignore_errors=True)
                    logger.info("✅ Removed %s", dir_path)
                except Exception as exc:
                    logger.warning("Could not remove %s: %s", dir_path, exc)

        # Exit the application
        QApplication.quit()

    # ------------------------------------------------------------------
    # UI Event Handlers
    # ------------------------------------------------------------------

    @Slot(int)
    def _on_volume_changed(self, volume: int) -> None:
        self._player.set_volume(volume)
        self._settings.set_volume(volume)

    @Slot(float)
    def _on_speed_changed(self, speed: float) -> None:
        self._player.set_playback_rate(speed)
        self._settings.set_playback_rate(speed)

    @Slot(str, str, int)
    def _on_proxy_configured(self, proxy_type: str, server: str, port: int) -> None:
        self._settings.set_proxy(proxy_type, server, port, enabled=True)
        if proxy_type == "SOCKS5":
            self._telegram.set_socks5_proxy(server, port)
        else:
            self._telegram.set_http_proxy(server, port)

    @Slot(OwnedChat)
    def _on_chat_selected(self, chat: OwnedChat) -> None:
        logger.info("User selected chat: %s (ID: %d). Loading initial tracks chunk...", chat.title, chat.id)
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

    @Slot(object, list)
    def _on_tracks_deleted(self, chat_id: int, deleted_track_ids: list[str]) -> None:
        self._main_view.remove_tracks(chat_id, deleted_track_ids)
        self._player.remove_from_playlist(chat_id, deleted_track_ids)

    @Slot(Track)
    def _on_track_selected(self, track: Track) -> None:
        self._player.play_track(track)

    @Slot(str)
    def _on_auth_state_changed(self, state: str) -> None:
        logger.info("Main window reacting to auth state: %s", state)
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
                # Session terminated remotely -> perform full logout (wipe data and exit)
                logger.info("Session terminated remotely. Performing full logout...")
                self._on_perform_logout()

    @Slot()
    def _on_track_label_clicked(self) -> None:
        track = self._player.current_track
        if track:
            self._main_view.scroll_to_track(track)


# ------------------------------------------------------------------
# Application Entry Point
# ------------------------------------------------------------------

def main() -> int:
    config = AppConfig()
    setup_logging(config, is_dev=True)

    logger.info("Starting %s v%s...", config.app_name, config.app_version)

    app = create_application(config)

    crypto_manager = CryptoManager(config.app_data_dir)
    settings_service = SettingsService(config, crypto_manager)

    tdlib_adapter = TDLibAdapter()
    stream_server = LocalStreamServer(tdlib_adapter)

    cache_manager = CacheManager(config, crypto_manager, tdlib_adapter)

    telegram_service = TelegramService(config, tdlib_adapter, settings_service, cache_manager)

    player_service = PlayerService(config, telegram_service, settings_service, cache_manager, stream_server)

    network_meter = NetworkMeter()

    window = MainWindow(
        config,
        telegram_service,
        player_service,
        cache_manager,
        network_meter,
        settings_service,
        stream_server,
        tdlib_adapter,
    )
    window.show()

    telegram_service.start()

    exit_code = app.exec()

    stream_server.stop()
    telegram_service.stop()
    tdlib_adapter.close()
    logger.info("Application exited cleanly with code %d", exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())