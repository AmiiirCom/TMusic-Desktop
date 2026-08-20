from PySide6.QtCore import QEvent, QPoint, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.config import AppConfig
from app.core.metadata import AudioMetadata
from app.models.track import Track
from app.ui.components.player_controls import SPEED_OPTIONS, PlayerControls
from app.ui.utils.pixmaps import create_rounded_cover_pixmap


class PlayerBar(QFrame):
    """Bottom audio player bar with track info, playback controls, and sound adjustments."""

    play_pause_clicked = Signal()
    next_clicked = Signal()
    previous_clicked = Signal()
    seek_requested = Signal(int)
    volume_changed = Signal(int)
    speed_changed = Signal(float)
    lyrics_clicked = Signal()
    track_info_clicked = Signal()
    track_label_clicked = Signal()
    like_clicked = Signal()

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self.setFixedHeight(84)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._current_track: Track | None = None
        self._cover_path: str | None = None
        self._current_speed = 1.0
        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            PlayerBar {
                background-color: #17212b;
                border-top: 1px solid #0e1621;
            }
            QLabel {
                color: #ffffff;
                font-family: 'Segoe UI', 'Vazirmatn', sans-serif;
            }
            QPushButton {
                background: transparent;
                border: none;
                color: #ffffff;
                font-size: 16px;
                padding: 4px;
                border-radius: 18px;
            }
            QPushButton:hover { background-color: #242f3d; }
            QPushButton#btnPlayPause {
                background-color: #2481cc;
                font-size: 18px;
                font-weight: bold;
                min-width: 38px;
                min-height: 38px;
                border-radius: 19px;
            }
            QPushButton#btnPlayPause:hover { background-color: #1d72b8; }
            QPushButton#btnPlayerLike {
                background: transparent;
                border: none;
                font-size: 16px;
                border-radius: 16px;
                min-width: 32px;
                min-height: 32px;
            }
            QPushButton#btnPlayerLike:hover { background-color: #242f3d; }
            QPushButton#btnSpeed {
                background-color: #242f3d;
                color: #6ab3f3;
                font-size: 12px;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 6px;
                min-width: 44px;
            }
            QPushButton#btnSpeed:hover {
                background-color: #2f3e50;
                color: #ffffff;
            }
            QPushButton#btnLyrics {
                background-color: #242f3d;
                font-size: 12px;
                font-weight: bold;
                padding: 4px 10px;
                border-radius: 6px;
                color: #ffffff;
            }
            QPushButton#btnLyrics:disabled {
                background-color: transparent;
                color: #4a5768;
            }
            QPushButton#btnLyrics:enabled {
                color: #6ab3f3;
                border: 1px solid #2481cc;
            }
            QPushButton#btnInfo {
                font-size: 12px;
                font-weight: bold;
                padding: 4px 8px;
                color: #7f91a4;
            }
            QPushButton#btnInfo:hover { color: #ffffff; }
            QSlider::groove:horizontal {
                height: 4px;
                background: #242f3d;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #2481cc;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                width: 10px;
                height: 10px;
                margin: -3px 0;
                border-radius: 5px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(16)

        self.info_container = QWidget(self)
        self.info_container.installEventFilter(self)
        self.info_container.setFixedWidth(280)
        info_layout = QHBoxLayout(self.info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(10)

        self.artwork_badge = QLabel()
        self.artwork_badge.setFixedSize(48, 48)
        self.artwork_badge.setPixmap(create_rounded_cover_pixmap(size=48))

        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(2)
        meta_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.title_label = QLabel(self.tr("No track playing"))
        self.title_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        self.artist_label = QLabel(f"{self._config.app_name} Desktop")
        self.artist_label.setStyleSheet("font-size: 11px; color: #7f91a4;")

        meta_layout.addWidget(self.title_label)
        meta_layout.addWidget(self.artist_label)

        self.btn_like = QPushButton("🤍")
        self.btn_like.setObjectName("btnPlayerLike")
        self.btn_like.setFixedSize(34, 34)
        self.btn_like.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_like.setEnabled(False)
        self.btn_like.clicked.connect(self.like_clicked.emit)

        info_layout.addWidget(self.artwork_badge)
        info_layout.addLayout(meta_layout, stretch=1)
        info_layout.addWidget(self.btn_like)
        layout.addWidget(self.info_container)

        self.controls = PlayerControls(self)
        self.controls.play_pause_clicked.connect(self.play_pause_clicked.emit)
        self.controls.next_clicked.connect(self.next_clicked.emit)
        self.controls.previous_clicked.connect(self.previous_clicked.emit)
        self.controls.seek_requested.connect(self.seek_requested.emit)
        layout.addWidget(self.controls, stretch=1)

        right_container = QWidget(self)
        right_container.setFixedWidth(280)
        right_layout = QHBoxLayout(right_container)
        right_layout.setSpacing(8)

        self.btn_lyrics = QPushButton(self.tr("Lyrics"))
        self.btn_lyrics.setObjectName("btnLyrics")
        self.btn_lyrics.setEnabled(False)
        self.btn_lyrics.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_lyrics.clicked.connect(self.lyrics_clicked.emit)

        self.btn_info = QPushButton(self.tr("Info"))
        self.btn_info.setObjectName("btnInfo")
        self.btn_info.setEnabled(False)
        self.btn_info.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_info.clicked.connect(self.track_info_clicked.emit)

        self.btn_speed = QPushButton("1.0x")
        self.btn_speed.setObjectName("btnSpeed")
        self.btn_speed.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_speed.clicked.connect(self._open_speed_menu)

        vol_icon = QLabel("Vol")
        vol_icon.setStyleSheet("color: #7f91a4; font-size: 11px; font-weight: bold;")
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.valueChanged.connect(self.volume_changed.emit)

        right_layout.addWidget(self.btn_lyrics)
        right_layout.addWidget(self.btn_info)
        right_layout.addWidget(self.btn_speed)
        right_layout.addWidget(vol_icon)
        right_layout.addWidget(self.vol_slider)
        layout.addWidget(right_container)

    def eventFilter(self, obj, event):
        if obj == self.info_container and event.type() == QEvent.Type.MouseButtonPress:
            if not self.btn_like.geometry().contains(event.position().toPoint()):
                self.track_label_clicked.emit()
                return True
        return super().eventFilter(obj, event)

    def _open_speed_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #17212b;
                color: #ffffff;
                border: 1px solid #2f3e50;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 24px;
                border-radius: 4px;
                font-size: 13px;
            }
            QMenu::item:selected { background-color: #2481cc; }
        """)

        for speed in SPEED_OPTIONS:
            label = f"{speed}x Normal" if speed == 1.0 else f"{speed}x"
            action = QAction(label, menu)
            if abs(speed - self._current_speed) < 0.01:
                action.setText(f"✓  {label}")
            action.triggered.connect(lambda checked=False, s=speed: self._on_select_speed(s))
            menu.addAction(action)

        btn_pos = self.btn_speed.mapToGlobal(QPoint(0, 0))
        menu.exec(QPoint(btn_pos.x(), btn_pos.y() - menu.sizeHint().height() - 6))

    def _on_select_speed(self, speed: float) -> None:
        self.set_playback_rate(speed)
        self.speed_changed.emit(speed)

    def set_playback_rate(self, speed: float) -> None:
        self._current_speed = speed
        self.btn_speed.setText(f"{speed}x")

    def set_track(self, track: Track | None) -> None:
        if track is None:
            self.reset_track()
            return

        self._current_track = track
        self._cover_path = track.cover_path
        self.title_label.setText(track.display_title)
        self.artist_label.setText(track.display_artist)
        self.controls.set_duration(track.duration_seconds * 1000)
        self.btn_info.setEnabled(True)
        self.btn_lyrics.setEnabled(False)
        self.btn_like.setEnabled(True)
        self.update_reaction(track.is_liked, track.heart_count)
        self.update_cover(self._cover_path)

    def reset_track(self) -> None:
        self._current_track = None
        self._cover_path = None
        self.title_label.setText(self.tr("No track playing"))
        self.artist_label.setText(f"{self._config.app_name} Desktop")
        self.controls.set_position(0)
        self.controls.set_duration(0)
        self.controls.set_playback_state(False)
        self.btn_lyrics.setEnabled(False)
        self.btn_info.setEnabled(False)
        self.btn_like.setEnabled(False)
        self.btn_like.setText("🤍")
        self.artwork_badge.setPixmap(create_rounded_cover_pixmap(size=48))

    def update_reaction(self, is_liked: bool, heart_count: int) -> None:
        self.btn_like.setText("❤️" if is_liked else "🤍")
        tip = self.tr("Liked") if is_liked else self.tr("Like")
        self.btn_like.setToolTip(tip)

    def update_metadata(self, metadata: AudioMetadata) -> None:
        self.btn_lyrics.setEnabled(metadata.has_lyrics)

    def update_cover(self, cover_path: str | None) -> None:
        if cover_path:
            self._cover_path = cover_path
        minithumb = self._current_track.minithumbnail_data if self._current_track else None
        active = self._cover_path or (self._current_track.cover_path if self._current_track else None)
        self.artwork_badge.setPixmap(create_rounded_cover_pixmap(minithumb_data=minithumb, cover_path=active, size=48))

    def set_playback_state(self, is_playing: bool) -> None:
        self.controls.set_playback_state(is_playing)

    def set_position(self, position_ms: int) -> None:
        self.controls.set_position(position_ms)

    def set_duration(self, duration_ms: int) -> None:
        self.controls.set_duration(duration_ms)