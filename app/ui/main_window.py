import logging
from pathlib import Path
import shutil
from typing import Any
from PySide6.QtCore import QEvent, QObject, QPoint, Qt, Slot
from PySide6.QtGui import QCloseEvent, QCursor, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.cache.service import CacheManager
from app.config import AppConfig
from app.models.chat import FAVORITES_CHAT_ID, OwnedChat
from app.models.track import Track
from app.network.meter import NetworkMeter
from app.network.stream_server import LocalStreamServer
from app.player.service import PlayerService
from app.platform.tray_service import TrayService
from app.settings.service import ProxySettings, SettingsService
from app.telegram.adapter import TDLibAdapter
from app.telegram.enums import AuthState
from app.telegram.service import TelegramService
from app.ui.components.title_bar import CustomTitleBar
from app.ui.utils.animations import fade_in_widget
from app.ui.views.login_view import LoginView
from app.ui.views.lyrics_dialog import LyricsDialog
from app.ui.views.main_view import MainView
from app.ui.views.proxy_dialog import ProxyDialog
from app.ui.views.settings_dialog import SettingsDialog
from app.ui.views.track_info_dialog import TrackInfoDialog
from app.ui.utils.icons import get_application_icon

logger = logging.getLogger("tmusic.main_window")

# Border margin width (in pixels) for responsive edge resizing
RESIZE_BORDER_MARGIN = 8


def has_saved_telegram_session(config: AppConfig) -> bool:
    td_binlog = config.tdlib_dir / "td.binlog"
    return td_binlog.exists() and td_binlog.stat().st_size > 0


class MainWindow(QMainWindow):
    """
    Root frameless application window featuring custom Telegram-styled titlebar,
    10px rounded corners, native 8-direction edge resizing with global event filtering, and tray integration.
    """

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
        self._is_resizing_cursor_active = False

        # Frameless window configuration
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle(f"{config.app_name} Desktop")
        self.setWindowIcon(get_application_icon())
        self.resize(1100, 750)
        self.setMinimumSize(850, 560)
        self.setMouseTracking(True)

        # Root Container
        self._root_widget = QWidget(self)
        self._root_widget.setObjectName("rootContainer")
        self._root_widget.setMouseTracking(True)
        self.setCentralWidget(self._root_widget)

        root_layout = QVBoxLayout(self._root_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Custom Telegram TitleBar
        self._title_bar = CustomTitleBar(self._config, self)
        self._title_bar.minimize_requested.connect(self.showMinimized)
        self._title_bar.maximize_restore_requested.connect(self._toggle_maximize_restore)
        self._title_bar.close_requested.connect(self.close)
        root_layout.addWidget(self._title_bar)

        # 2. Central Content Stack
        self._central_stack = QStackedWidget(self._root_widget)
        self._central_stack.setMouseTracking(True)

        self._main_view = MainView(self._config, self)
        self._login_view = LoginView(self._config, self)

        self._central_stack.addWidget(self._main_view)
        self._central_stack.addWidget(self._login_view)

        if has_saved_telegram_session(self._config):
            self._central_stack.setCurrentWidget(self._main_view)
        else:
            self._central_stack.setCurrentWidget(self._login_view)

        root_layout.addWidget(self._central_stack, stretch=1)

        self._apply_window_frame_style(False)
        self._connect_signals()
        self._restore_preferences()

        self._tray = TrayService(self, self._player, self._config)
        self._tray.show_window_requested.connect(self._restore_window)
        self._tray.quit_requested.connect(self._quit_application)

        self._telegram.load_cached_state()
        self._apply_saved_proxy()

        # Install global application event filter for reliable 8-direction edge resizing
        if (app := QApplication.instance()) is not None:
            app.installEventFilter(self)

    def _apply_window_frame_style(self, is_max: bool) -> None:
        radius = "0px" if is_max else "10px"
        border = "none" if is_max else "1px solid #242f3d"
        self._root_widget.setStyleSheet(f"""
            QWidget#rootContainer {{
                background-color: #0e1621;
                border: {border};
                border-radius: {radius};
            }}
        """)
        self._title_bar.set_maximized(is_max)

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

    def _toggle_maximize_restore(self) -> None:
        if self.isMaximized():
            self.showNormal()
            self._apply_window_frame_style(False)
        else:
            self.showMaximized()
            self._apply_window_frame_style(True)

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.WindowStateChange:
            self._apply_window_frame_style(self.isMaximized())
        super().changeEvent(event)

    # ------------------------------------------------------------------
    # Robust 8-Direction Native Border Resizing & Cursor Handling
    # ------------------------------------------------------------------

    def _calculate_resize_edge(self, global_pos: QPoint) -> Qt.Edge | None:
        if self.isMaximized():
            return None

        local_pos = self.mapFromGlobal(global_pos)
        x, y = local_pos.x(), local_pos.y()
        w, h = self.width(), self.height()

        if x < 0 or x > w or y < 0 or y > h:
            return None

        m = RESIZE_BORDER_MARGIN

        on_left = x <= m
        on_right = x >= w - m
        on_top = y <= m
        on_bottom = y >= h - m

        if on_top and on_left:
            return Qt.Edge.TopEdge | Qt.Edge.LeftEdge
        if on_top and on_right:
            return Qt.Edge.TopEdge | Qt.Edge.RightEdge
        if on_bottom and on_left:
            return Qt.Edge.BottomEdge | Qt.Edge.LeftEdge
        if on_bottom and on_right:
            return Qt.Edge.BottomEdge | Qt.Edge.RightEdge
        if on_left:
            return Qt.Edge.LeftEdge
        if on_right:
            return Qt.Edge.RightEdge
        if on_top:
            return Qt.Edge.TopEdge
        if on_bottom:
            return Qt.Edge.BottomEdge
        return None

    def _update_resize_cursor(self, edge: Qt.Edge | None) -> None:
        if edge is None:
            if self._is_resizing_cursor_active:
                self._is_resizing_cursor_active = False
                self.unsetCursor()
            return

        self._is_resizing_cursor_active = True

        if edge in (
            Qt.Edge.TopEdge | Qt.Edge.LeftEdge,
            Qt.Edge.BottomEdge | Qt.Edge.RightEdge,
        ):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edge in (
            Qt.Edge.TopEdge | Qt.Edge.RightEdge,
            Qt.Edge.BottomEdge | Qt.Edge.LeftEdge,
        ):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif edge in (Qt.Edge.LeftEdge, Qt.Edge.RightEdge):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edge in (Qt.Edge.TopEdge, Qt.Edge.BottomEdge):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.unsetCursor()
            self._is_resizing_cursor_active = False

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Global application event filter catching edge interactions before child widgets swallow them."""
        if not self.isVisible() or self.isMaximized():
            if self._is_resizing_cursor_active:
                self._is_resizing_cursor_active = False
                self.unsetCursor()
            return super().eventFilter(watched, event)

        if not isinstance(watched, QWidget) or watched.window() != self:
            return super().eventFilter(watched, event)

        etype = event.type()

        if etype in (QEvent.Type.MouseMove, QEvent.Type.HoverMove):
            global_pos = QCursor.pos()
            edge = self._calculate_resize_edge(global_pos)
            self._update_resize_cursor(edge)

        elif etype == QEvent.Type.MouseButtonPress:
            if isinstance(event, QMouseEvent) and event.button() == Qt.MouseButton.LeftButton:
                global_pos = event.globalPosition().toPoint()
                edge = self._calculate_resize_edge(global_pos)
                if edge is not None:
                    win_handle = self.windowHandle()
                    if win_handle and win_handle.startSystemResize(edge):
                        return True

        elif etype == QEvent.Type.Leave:
            if watched == self or watched == self._root_widget:
                self._update_resize_cursor(None)

        return super().eventFilter(watched, event)

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
            self._tray.show_message("TMusic", self.tr("Playing in background"))
        else:
            if (app := QApplication.instance()) is not None:
                app.removeEventFilter(self)
            event.accept()

    def _restore_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self._telegram.set_online_status(True)

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
        """Completely wipe session, database, logs, and caches (preserving TMusicDownloads) and quit."""
        self._is_quitting = True

        # 1. Stop audio playback immediately
        if self._player.is_playing:
            self._player.stop()

        # 2. Stop Telegram, Streaming Server and TDLib workers
        try:
            self._telegram.stop()
            self._stream_server.stop()
            self._tdlib_adapter.close()
        except Exception as exc:
            logger.warning("Shutdown error: %s", exc)

        # 3. Explicitly shut down logging handlers to release file lock on tmusic.log
        try:
            logging.shutdown()
        except Exception:
            pass

        # 4. Wipe AppData, TDLib database, cache, and thumbnails (PRESERVING downloads_dir)
        dirs_to_wipe = [
            self._config.tdlib_dir,
            self._config.tdlib_files_dir,
            self._config.thumb_cache_dir,
            self._config.cache_dir,
            self._config.app_data_dir,
        ]

        for target_dir in dirs_to_wipe:
            if target_dir.exists():
                try:
                    shutil.rmtree(target_dir, ignore_errors=True)
                except Exception:
                    pass

        # Also wipe master org roots if they exist
        for org_root in (self._config.org_data_root, self._config.org_cache_root):
            if org_root.exists():
                try:
                    shutil.rmtree(org_root, ignore_errors=True)
                except Exception:
                    pass

        # 5. Cleanly terminate the application process
        app = QApplication.instance()
        if app is not None:
            app.quit()
        import sys
        sys.exit(0)

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
        active = self._main_view._active_chat
        if active is not None:
            is_curr_chat = (active.id == chat_id)
            is_fav = (active.is_favorites and chat_id == FAVORITES_CHAT_ID)
            if is_curr_chat or is_fav:
                self._main_view.set_initial_tracks(tracks, has_more=has_more)
                self._player.set_playlist(tracks)

    @Slot(object, list, bool)
    def _on_tracks_appended(self, chat_id: int, new_tracks: list[Track], has_more: bool) -> None:
        active = self._main_view._active_chat
        if active is not None:
            is_curr_chat = (active.id == chat_id)
            is_fav = (active.is_favorites and chat_id == FAVORITES_CHAT_ID)
            if is_curr_chat or is_fav:
                self._main_view.append_tracks(new_tracks, has_more=has_more)
                self._player.append_to_playlist(new_tracks)

    @Slot(object, list)
    def _on_tracks_prepended(self, chat_id: int, new_tracks: list[Track]) -> None:
        active = self._main_view._active_chat
        if active is not None:
            is_curr_chat = (active.id == chat_id)
            is_fav = (active.is_favorites and chat_id == FAVORITES_CHAT_ID)
            if is_curr_chat or is_fav:
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

    def _switch_main_stack(self, widget: QWidget) -> None:
        if self._central_stack.currentWidget() != widget:
            self._central_stack.setCurrentWidget(widget)
            fade_in_widget(self._central_stack.currentWidget(), duration_ms=220)

    @Slot(str)
    def _on_auth_state_changed(self, state: str) -> None:
        match state:
            case AuthState.WAIT_PHONE_NUMBER | AuthState.LOGGING_OUT:
                self._switch_main_stack(self._login_view)
                self._login_view.show_phone_step()
            case AuthState.WAIT_CODE:
                self._switch_main_stack(self._login_view)
                self._login_view.show_code_step()
            case AuthState.WAIT_PASSWORD:
                self._switch_main_stack(self._login_view)
                self._login_view.show_password_step()
            case AuthState.READY:
                self._switch_main_stack(self._main_view)
            case AuthState.CLOSED:
                self._on_perform_logout()

    @Slot()
    def _on_track_label_clicked(self) -> None:
        track = self._player.current_track
        if track:
            self._main_view.scroll_to_track(track)