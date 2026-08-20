
import logging
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from app.config import AppConfig
from app.models.track import Track
from app.player.service import PlayerService

logger = logging.getLogger("tmusic.platform.tray")


def create_default_tray_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    painter.setBrush(QColor("#2481cc"))
    painter.setPen(QColor(0, 0, 0, 0))
    painter.drawEllipse(2, 2, 60, 60)

    painter.setPen(QColor("#ffffff"))
    font = QFont("Segoe UI Emoji", 24, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), 0x0084, "🎵")
    painter.end()

    return QIcon(pixmap)


class TrayService(QObject):
    """System tray integration with background playback actions and menu controls."""

    show_window_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent_widget: QWidget, player_service: PlayerService, config: AppConfig) -> None:
        super().__init__(parent_widget)
        self._parent = parent_widget
        self._player = player_service
        self._config = config

        self._tray = QSystemTrayIcon(create_default_tray_icon(), parent_widget)
        self._tray.setToolTip(f"{self._config.app_name} Desktop")

        self._init_menu()
        self._tray.activated.connect(self._on_activated)

        self._player.track_changed.connect(self._on_track_changed)
        self._player.playback_state_changed.connect(self._on_playback_state_changed)

        self._tray.show()
        logger.info("System Tray initialized.")

    def _init_menu(self) -> None:
        menu = QMenu(self._parent)
        menu.setStyleSheet("""
            QMenu {
                background-color: #17212b;
                color: #ffffff;
                border: 1px solid #2f3e50;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #2481cc;
            }
            QMenu::separator {
                height: 1px;
                background: #242f3d;
                margin: 4px 8px;
            }
        """)

        self.track_info_action = QAction(f"🎵 {self._config.app_name} Player", menu)
        self.track_info_action.setEnabled(False)
        menu.addAction(self.track_info_action)
        menu.addSeparator()

        self.play_pause_action = QAction("پخش (Play)", menu)
        self.play_pause_action.triggered.connect(self._player.toggle_play_pause)
        menu.addAction(self.play_pause_action)

        next_action = QAction("آهنگ بعدی (Next)", menu)
        next_action.triggered.connect(self._player.play_next)
        menu.addAction(next_action)

        prev_action = QAction("آهنگ قبلی (Previous)", menu)
        prev_action.triggered.connect(self._player.play_previous)
        menu.addAction(prev_action)

        menu.addSeparator()

        show_action = QAction("نمایش پنجره اصلی", menu)
        show_action.triggered.connect(self.show_window_requested.emit)
        menu.addAction(show_action)

        quit_action = QAction("خروج کامل (Exit)", menu)
        quit_action.triggered.connect(self.quit_requested.emit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_window_requested.emit()

    def _on_track_changed(self, track: Track | None) -> None:
        if track is None:
            self.track_info_action.setText(f"🎵 {self._config.app_name} Player")
            self._tray.setToolTip(f"{self._config.app_name} Desktop")
            return

        self.track_info_action.setText(f"🎵 {track.display_title[:25]}")
        self._tray.setToolTip(f"{self._config.app_name}: {track.display_title} - {track.display_artist}")

    def _on_playback_state_changed(self, is_playing: bool) -> None:
        self.play_pause_action.setText("توقف (Pause)" if is_playing else "پخش (Play)")

    def show_message(self, title: str, message: str) -> None:
        self._tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 2000)