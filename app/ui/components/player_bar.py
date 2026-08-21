from PySide6.QtCore import QEvent, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QAction, QFont, QIcon, QPixmap
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
from app.ui.components.marquee_label import MarqueeLabel
from app.ui.components.player_controls import SPEED_OPTIONS, PlayerControls
from app.ui.utils.icons import get_svg_icon, get_svg_pixmap
from app.ui.utils.pixmaps import create_rounded_cover_pixmap


class PlayerBar(QFrame):
    """Bottom audio player bar with balanced icons, marquee info, and controls."""

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
                background: transparent;
                background-color: transparent;
                border: none;
            }
            QPushButton#btnPlayerIconAction {
                background-color: transparent;
                border: none;
                border-radius: 16px;
            }
            QPushButton#btnPlayerIconAction:hover {
                background-color: rgba(255, 255, 255, 0.08);
            }
            QPushButton#btnPlayerIconAction:pressed {
                background-color: rgba(255, 255, 255, 0.16);
            }
            QPushButton#btnPlayerLike {
                background: transparent;
                border: none;
                border-radius: 17px;
            }
            QPushButton#btnPlayerLike:hover {
                background-color: rgba(229, 57, 53, 0.15);
            }
            QPushButton#btnPlayerLike:pressed {
                background-color: rgba(229, 57, 53, 0.25);
            }
            QPushButton#btnSpeed {
                background-color: #242f3d;
                color: #6ab3f3;
                font-size: 11px;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 6px;
                border: 1px solid #2f3e50;
                min-width: 38px;
                max-height: 24px;
            }
            QPushButton#btnSpeed:hover {
                background-color: #2b394a;
                border-color: #3f546c;
                color: #ffffff;
            }
            QPushButton#btnSpeed:pressed {
                background-color: #1e2834;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(14)

        # Left Area: Artwork, Title/Artist, and Like Button
        self.info_container = QWidget(self)
        self.info_container.installEventFilter(self)
        self.info_container.setFixedWidth(270)
        info_layout = QHBoxLayout(self.info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(10)

        self.artwork_badge = QLabel()
        self.artwork_badge.setFixedSize(46, 46)
        self.artwork_badge.setPixmap(create_rounded_cover_pixmap(size=46))

        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(2)
        meta_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.title_label = MarqueeLabel(self.tr("No track playing"), fade_width=14, speed_px_per_sec=30)
        self.title_label.setFixedHeight(20)
        title_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        self.title_label.setFont(title_font)
        self.title_label.setTextColor("#ffffff")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.artist_label = MarqueeLabel(f"{self._config.app_name} Desktop", fade_width=12, speed_px_per_sec=26)
        self.artist_label.setFixedHeight(16)
        artist_font = QFont("Segoe UI", 9)
        self.artist_label.setFont(artist_font)
        self.artist_label.setTextColor("#8192a5")
        self.artist_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        meta_layout.addWidget(self.title_label)
        meta_layout.addWidget(self.artist_label)

        self.btn_like = QPushButton()
        self.btn_like.setObjectName("btnPlayerLike")
        self.btn_like.setFixedSize(34, 34)
        self.btn_like.setIcon(get_svg_icon("heart_outline", "#8192a5", 18))
        self.btn_like.setIconSize(QSize(18, 18))
        self.btn_like.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_like.setEnabled(False)
        self.btn_like.clicked.connect(self._on_like_button_clicked)

        info_layout.addWidget(self.artwork_badge)
        info_layout.addLayout(meta_layout, stretch=1)
        info_layout.addWidget(self.btn_like)
        layout.addWidget(self.info_container)

        # Center Area: Main Playback Controls & Timeline
        self.controls = PlayerControls(self)
        self.controls.play_pause_clicked.connect(self.play_pause_clicked.emit)
        self.controls.next_clicked.connect(self.next_clicked.emit)
        self.controls.previous_clicked.connect(self.previous_clicked.emit)
        self.controls.seek_requested.connect(self.seek_requested.emit)
        layout.addWidget(self.controls, stretch=1)

        # Right Area: Lyrics, Info, Speed, and Volume
        right_container = QWidget(self)
        right_container.setFixedWidth(270)
        right_layout = QHBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

        self.btn_lyrics = QPushButton()
        self.btn_lyrics.setObjectName("btnPlayerIconAction")
        self.btn_lyrics.setFixedSize(32, 32)
        self.btn_lyrics.setIcon(get_svg_icon("lyrics", "#8192a5", 16))
        self.btn_lyrics.setIconSize(QSize(16, 16))
        self.btn_lyrics.setToolTip(self.tr("Lyrics"))
        self.btn_lyrics.setEnabled(False)
        self.btn_lyrics.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_lyrics.clicked.connect(self.lyrics_clicked.emit)

        self.btn_info = QPushButton()
        self.btn_info.setObjectName("btnPlayerIconAction")
        self.btn_info.setFixedSize(32, 32)
        self.btn_info.setIcon(get_svg_icon("info", "#8192a5", 16))
        self.btn_info.setIconSize(QSize(16, 16))
        self.btn_info.setToolTip(self.tr("Track Details"))
        self.btn_info.setEnabled(False)
        self.btn_info.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_info.clicked.connect(self.track_info_clicked.emit)

        self.btn_speed = QPushButton("1.0x")
        self.btn_speed.setObjectName("btnSpeed")
        self.btn_speed.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_speed.clicked.connect(self._open_speed_menu)

        vol_icon = QLabel()
        vol_icon.setFixedSize(16, 16)
        vol_icon.setPixmap(get_svg_pixmap("volume", "#8192a5", 16))

        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setFixedWidth(75)
        self.vol_slider.valueChanged.connect(self.volume_changed.emit)

        right_layout.addWidget(self.btn_lyrics)
        right_layout.addWidget(self.btn_info)
        right_layout.addSpacing(4)
        right_layout.addWidget(self.btn_speed)
        right_layout.addSpacing(4)
        right_layout.addWidget(vol_icon)
        right_layout.addWidget(self.vol_slider)
        layout.addWidget(right_container)

    def eventFilter(self, obj, event):
        if obj == self.info_container and event.type() == QEvent.Type.MouseButtonPress:
            if not self.btn_like.geometry().contains(event.position().toPoint()):
                self.track_label_clicked.emit()
                return True
        return super().eventFilter(obj, event)

    def _on_like_button_clicked(self) -> None:
        if self._current_track:
            self.like_clicked.emit()

    def _open_speed_menu(self) -> None:
        menu = QMenu(self)
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
            }
            QMenu::item:selected {
                background-color: #2481cc;
            }
        """)

        empty_pixmap = QPixmap(14, 14)
        empty_pixmap.fill(Qt.GlobalColor.transparent)
        empty_icon = QIcon(empty_pixmap)

        for speed in SPEED_OPTIONS:
            label = f"{speed}x Normal" if speed == 1.0 else f"{speed}x"
            action = QAction(label, menu)
            if abs(speed - self._current_speed) < 0.01:
                action.setIcon(get_svg_icon("check", "#52a3ff", 14))
            else:
                action.setIcon(empty_icon)

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
        self.btn_like.setIcon(get_svg_icon("heart_outline", "#8192a5", 18))
        self.artwork_badge.setPixmap(create_rounded_cover_pixmap(size=46))

    def update_reaction(self, is_liked: bool, heart_count: int) -> None:
        if is_liked:
            self.btn_like.setIcon(get_svg_icon("heart_filled", "#e53935", 18))
        else:
            self.btn_like.setIcon(get_svg_icon("heart_outline", "#8192a5", 18))
        tip = self.tr("Liked") if is_liked else self.tr("Like")
        self.btn_like.setToolTip(tip)

    def update_metadata(self, metadata: AudioMetadata) -> None:
        self.btn_lyrics.setEnabled(metadata.has_lyrics)
        if metadata.has_lyrics:
            self.btn_lyrics.setIcon(get_svg_icon("lyrics", "#52a3ff", 16))
        else:
            self.btn_lyrics.setIcon(get_svg_icon("lyrics", "#8192a5", 16))

    def update_cover(self, cover_path: str | None) -> None:
        if cover_path:
            self._cover_path = cover_path
        minithumb = self._current_track.minithumbnail_data if self._current_track else None
        active = self._cover_path or (self._current_track.cover_path if self._current_track else None)
        self.artwork_badge.setPixmap(create_rounded_cover_pixmap(minithumb_data=minithumb, cover_path=active, size=46))

    def set_playback_state(self, is_playing: bool) -> None:
        self.controls.set_playback_state(is_playing)

    def set_position(self, position_ms: int) -> None:
        self.controls.set_position(position_ms)

    def set_duration(self, duration_ms: int) -> None:
        self.controls.set_duration(duration_ms)