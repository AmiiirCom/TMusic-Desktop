import logging
import sys
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from app.bootstrap import create_application
from app.cache.service import CacheService
from app.config import AppConfig
from app.core.logger import setup_logging
from app.core.security import CryptoManager
from app.models.chat import OwnedChat
from app.models.track import Track
from app.models.user import TelegramUser
from app.network.meter import NetworkMeter
from app.player.service import PlayerService
from app.platform.tray_service import TrayService
from app.settings.service import SettingsService
from app.telegram.adapter import TDLibAdapter
from app.telegram.enums import AuthState
from app.telegram.service import TelegramService
from app.ui.views.login_view import LoginView
from app.ui.views.main_view import MainView
from app.ui.views.settings_dialog import SettingsDialog

logger = logging.getLogger("tmusic.main")


class MainWindow(QMainWindow):
    def __init__(
        self,
        config: AppConfig,
        telegram_service: TelegramService,
        player_service: PlayerService,
        cache_service: CacheService,
        network_meter: NetworkMeter,
        settings_service: SettingsService,
    ) -> None:
        super().__init__()
        self._config = config
        self._telegram = telegram_service
        self._player = player_service
        self._cache = cache_service
        self._meter = network_meter
        self._settings = settings_service
        self._is_quitting = False

        self.setWindowTitle(f"{config.app_name} Desktop")
        self.resize(1100, 750)

        self._central_stack = QStackedWidget(self)
        self.setCentralWidget(self._central_stack)

        # 1. Login View
        self._login_view = LoginView(self)
        self._login_view.phone_submitted.connect(self._telegram.send_phone_number)
        self._login_view.code_submitted.connect(self._telegram.send_code)
        self._login_view.password_submitted.connect(self._telegram.send_password)
        self._login_view.proxy_configured.connect(self._on_proxy_configured)

        # 2. Main Dashboard View
        self._main_view = MainView(self)
        self._main_view.chat_selected.connect(self._on_chat_selected)
        self._main_view.track_selected.connect(self._on_track_selected)
        self._main_view.logout_requested.connect(self._telegram.log_out)
        self._main_view.settings_requested.connect(self._open_settings_dialog)

        # Connect PlayerBar UI controls with PlayerService
        player_bar = self._main_view.player_bar
        player_bar.play_pause_clicked.connect(self._player.toggle_play_pause)
        player_bar.next_clicked.connect(self._player.play_next)
        player_bar.previous_clicked.connect(self._player.play_previous)
        player_bar.seek_requested.connect(self._player.seek)
        player_bar.volume_changed.connect(self._on_volume_changed)

        # Restore saved volume preference
        saved_vol = self._settings.preferences.volume
        player_bar.vol_slider.setValue(saved_vol)
        self._player.set_volume(saved_vol)

        # Connect PlayerService feedback with PlayerBar & TrackList UI
        self._player.track_changed.connect(player_bar.set_track)
        self._player.track_changed.connect(self._main_view.set_active_track)
        self._player.playback_state_changed.connect(player_bar.set_playback_state)
        self._player.position_changed.connect(player_bar.set_position)
        self._player.duration_changed.connect(player_bar.set_duration)

        # Network meter integration
        self._meter.stats_updated.connect(self._main_view.set_network_stats)
        self._telegram.file_download_progress.connect(self._on_download_progress)

        self._central_stack.addWidget(self._login_view)
        self._central_stack.addWidget(self._main_view)

        # System Tray Integration
        self._tray = TrayService(self, self._player)
        self._tray.show_window_requested.connect(self._restore_window)
        self._tray.quit_requested.connect(self._quit_application)

        # Connect Telegram Service signals
        self._telegram.auth_state_changed.connect(self._on_auth_state_changed)
        self._telegram.auth_error.connect(self._login_view.show_error)
        self._telegram.connection_state_changed.connect(self._login_view.set_connection_status)
        self._telegram.user_loaded.connect(self._main_view.set_user)
        self._telegram.owned_chats_loaded.connect(self._main_view.set_owned_chats)
        self._telegram.tracks_loaded.connect(self._on_tracks_loaded)

        # Emit cached music channels immediately after signal connection
        self._telegram.load_cached_music_chats()

        # Apply saved proxy automatically on launch
        self._apply_saved_proxy()

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
            self._tray.show_message("TMusic", "برنامه در پس‌زمینه در حال پخش است 🎵")
        else:
            event.accept()

    def _restore_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _quit_application(self) -> None:
        self._is_quitting = True
        QApplication.quit()

    def _open_settings_dialog(self) -> None:
        dialog = SettingsDialog(self._cache, self._settings, self)
        dialog.proxy_saved.connect(self._on_proxy_configured)
        dialog.exec()

    @Slot(int)
    def _on_volume_changed(self, volume: int) -> None:
        self._player.set_volume(volume)
        self._settings.set_volume(volume)

    @Slot(int, int, int)
    def _on_download_progress(self, file_id: int, downloaded: int, total: int) -> None:
        self._meter.record_download(downloaded)

    @Slot(str, str, int)
    def _on_proxy_configured(self, proxy_type: str, server: str, port: int) -> None:
        self._settings.set_proxy(proxy_type, server, port, enabled=True)
        if proxy_type == "SOCKS5":
            self._telegram.set_socks5_proxy(server, port)
        else:
            self._telegram.set_http_proxy(server, port)

    @Slot(OwnedChat)
    def _on_chat_selected(self, chat: OwnedChat) -> None:
        logger.info("User selected chat: %s (ID: %d). Loading tracks...", chat.title, chat.id)
        self._settings.set_last_chat(chat.id)
        self._telegram.load_chat_tracks(chat.id, limit=100)

    @Slot(object, list)
    def _on_tracks_loaded(self, chat_id: int, tracks: list[Track]) -> None:
        self._main_view.set_tracks(tracks)
        self._player.set_playlist(tracks)

    @Slot(Track)
    def _on_track_selected(self, track: Track) -> None:
        self._player.play_track(track)

    @Slot(str)
    def _on_auth_state_changed(self, state: str) -> None:
        match state:
            case AuthState.WAIT_PHONE_NUMBER:
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


def main() -> int:
    config = AppConfig()
    setup_logging(config, is_dev=True)

    logger.info("Starting %s v%s...", config.app_name, config.app_version)

    app = create_application(config)

    crypto_manager = CryptoManager(config.data_dir)
    settings_service = SettingsService(config.data_dir, crypto_manager)

    tdlib_adapter = TDLibAdapter()
    telegram_service = TelegramService(config, tdlib_adapter, settings_service)

    player_service = PlayerService(telegram_service)
    cache_service = CacheService(config)
    network_meter = NetworkMeter()

    window = MainWindow(
        config,
        telegram_service,
        player_service,
        cache_service,
        network_meter,
        settings_service,
    )
    window.show()

    telegram_service.start()

    exit_code = app.exec()

    telegram_service.stop()
    tdlib_adapter.close()
    logger.info("Application exited cleanly with code %d", exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())