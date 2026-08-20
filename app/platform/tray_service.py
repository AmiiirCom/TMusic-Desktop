import logging
from PySide6.QtCore import QObject, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QSystemTrayIcon,
    QWidget,
    QWidgetAction,
)

from app.config import AppConfig
from app.models.track import Track
from app.player.service import PlayerService
from app.ui.components.marquee_label import MarqueeLabel
from app.ui.utils.icons import get_svg_icon, get_svg_pixmap, render_svg_to_painter

logger = logging.getLogger("tmusic.platform.tray")


def create_default_tray_icon() -> QIcon:
    """Generate multi-resolution crisp vector tray icon for Windows, macOS, and Linux."""
    icon = QIcon()
    for size in (16, 20, 24, 32, 48, 64):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        render_svg_to_painter(painter, "app_logo", QRectF(0, 0, size, size))
        painter.end()
        icon.addPixmap(pixmap)
    return icon


class TrayService(QObject):
    """System tray integration with left-aligned actions, multi-DPI SVG icon, and animated track info."""

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
        menu.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        menu.setStyleSheet("""
            QMenu {
                background-color: #17212b;
                color: #ffffff;
                border: 1px solid #2f3e50;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 18px 6px 12px;
                border-radius: 4px;
                font-size: 13px;
                text-align: left;
                background-color: transparent;
            }
            QMenu::item:selected {
                background-color: #2481cc;
            }
            QMenu::separator {
                height: 1px;
                background: #242f3d;
                margin: 4px 8px;
            }
            QLabel {
                background: transparent;
                background-color: transparent;
                border: none;
            }
        """)

        # 1. Top Left-Aligned Marquee Track Info Action
        self.track_info_action = QWidgetAction(menu)
        self.track_info_container = QWidget(menu)
        self.track_info_container.setFixedHeight(34)
        self.track_info_container.setFixedWidth(250)
        self.track_info_container.setStyleSheet("background: transparent; background-color: transparent;")

        t_layout = QHBoxLayout(self.track_info_container)
        t_layout.setContentsMargins(10, 4, 10, 4)
        t_layout.setSpacing(8)
        t_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        music_icon_lbl = QLabel(self.track_info_container)
        music_icon_lbl.setFixedSize(16, 16)
        music_icon_lbl.setStyleSheet("background: transparent; border: none;")
        music_icon_lbl.setPixmap(get_svg_pixmap("music", "#6ab3f3", 16))

        self.track_info_label = MarqueeLabel(
            self.tr("TMusic Player"),
            fade_width=14,
            speed_px_per_sec=30,
            alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            parent=self.track_info_container,
        )
        self.track_info_label.setFixedHeight(22)
        font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        self.track_info_label.setFont(font)
        self.track_info_label.setTextColor("#6ab3f3")

        t_layout.addWidget(music_icon_lbl)
        t_layout.addWidget(self.track_info_label, stretch=1)
        self.track_info_action.setDefaultWidget(self.track_info_container)
        menu.addAction(self.track_info_action)

        menu.addSeparator()

        # 2. Controls Actions with Vector SVG Icons
        self.play_pause_action = QAction(get_svg_icon("play", "#ffffff", 16), self.tr("Play"), menu)
        self.play_pause_action.triggered.connect(self._player.toggle_play_pause)
        menu.addAction(self.play_pause_action)

        next_action = QAction(get_svg_icon("next", "#8192a5", 16), self.tr("Next Track"), menu)
        next_action.triggered.connect(self._player.play_next)
        menu.addAction(next_action)

        prev_action = QAction(get_svg_icon("previous", "#8192a5", 16), self.tr("Previous Track"), menu)
        prev_action.triggered.connect(self._player.play_previous)
        menu.addAction(prev_action)

        menu.addSeparator()

        show_action = QAction(get_svg_icon("app_logo", "#2481cc", 16), self.tr("Show Window"), menu)
        show_action.triggered.connect(self.show_window_requested.emit)
        menu.addAction(show_action)

        quit_action = QAction(get_svg_icon("logout", "#e53935", 16), self.tr("Quit"), menu)
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
            self.track_info_label.setText(self.tr("TMusic Player"))
            self._tray.setToolTip(f"{self._config.app_name} Desktop")
            return

        display_text = f"{track.display_title} - {track.display_artist}"
        self.track_info_label.setText(display_text)
        self._tray.setToolTip(f"{self._config.app_name}: {display_text}")

    def _on_playback_state_changed(self, is_playing: bool) -> None:
        if is_playing:
            self.play_pause_action.setText(self.tr("Pause"))
            self.play_pause_action.setIcon(get_svg_icon("pause", "#ffffff", 16))
        else:
            self.play_pause_action.setText(self.tr("Play"))
            self.play_pause_action.setIcon(get_svg_icon("play", "#ffffff", 16))

    def show_message(self, title: str, message: str) -> None:
        self._tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 2000)