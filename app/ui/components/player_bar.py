from pathlib import Path
from PySide6.QtCore import QEvent, QPoint, Qt, Signal
from PySide6.QtGui import QAction, QColor, QPainter, QPainterPath, QPixmap
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

from app.core.metadata import AudioMetadata
from app.models.track import Track

SPEED_OPTIONS = (0.75, 1.0, 1.25, 1.5, 1.75)


def create_playerbar_cover_pixmap(
    minithumb_data: bytes | None = None,
    cover_path: str | None = None,
    size: int = 48,
) -> QPixmap:
    target = QPixmap(size, size)
    target.fill(QColor(0, 0, 0, 0))

    painter = QPainter(target)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    path = QPainterPath()
    path.addRoundedRect(0, 0, size, size, 8, 8)
    painter.setClipPath(path)

    has_drawn = False

    if cover_path and Path(cover_path).exists():
        src = QPixmap(str(cover_path))
        if not src.isNull():
            scaled = src.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - size) // 2
            y = (scaled.height() - size) // 2
            painter.drawPixmap(0, 0, scaled.copy(x, y, size, size))
            has_drawn = True

    if not has_drawn and minithumb_data:
        src = QPixmap()
        if src.loadFromData(minithumb_data):
            scaled = src.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - size) // 2
            y = (scaled.height() - size) // 2
            painter.drawPixmap(0, 0, scaled.copy(x, y, size, size))
            has_drawn = True

    if not has_drawn:
        painter.fillRect(0, 0, size, size, QColor("#2b5278"))
        painter.setPen(QColor("#ffffff"))
        painter.drawText(target.rect(), Qt.AlignmentFlag.AlignCenter, "🎵")

    painter.end()
    return target


class PlayerBar(QFrame):
    """Telegram Desktop styled bottom audio player bar with full reset support."""

    play_pause_clicked = Signal()
    next_clicked = Signal()
    previous_clicked = Signal()
    seek_requested = Signal(int)
    volume_changed = Signal(int)
    speed_changed = Signal(float)
    lyrics_clicked = Signal()
    track_info_clicked = Signal()
    track_label_clicked = Signal()  # Emitted when user clicks on cover or title

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(84)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._current_track: Track | None = None
        self._is_slider_dragging = False
        self._duration_ms = 0
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
                font-family: 'Vazirmatn', 'Segoe UI', sans-serif;
            }
            QPushButton {
                background: transparent;
                border: none;
                color: #ffffff;
                font-size: 16px;
                padding: 4px;
                border-radius: 18px;
            }
            QPushButton:hover {
                background-color: #242f3d;
            }
            QPushButton#btnPlayPause {
                background-color: #2481cc;
                font-size: 18px;
                font-weight: bold;
                min-width: 38px;
                min-height: 38px;
                border-radius: 19px;
            }
            QPushButton#btnPlayPause:hover {
                background-color: #1d72b8;
            }
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
                font-size: 14px;
                padding: 4px 8px;
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
                font-size: 15px;
                padding: 4px;
                color: #7f91a4;
            }
            QPushButton#btnInfo:hover {
                color: #ffffff;
            }
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

        # Left section: artwork and track info (clickable)
        info_container = QWidget(self)
        self.info_container = info_container
        self.info_container.installEventFilter(self)
        info_container.setFixedWidth(260)
        info_layout = QHBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(12)

        self.artwork_badge = QLabel()
        self.artwork_badge.setFixedSize(48, 48)
        self.artwork_badge.setPixmap(create_playerbar_cover_pixmap(size=48))

        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(2)
        meta_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.title_label = QLabel("آهنگی در حال پخش نیست")
        self.title_label.setStyleSheet("font-size: 13px; font-weight: bold;")

        self.artist_label = QLabel("TMusic Desktop")
        self.artist_label.setStyleSheet("font-size: 11px; color: #7f91a4;")

        meta_layout.addWidget(self.title_label)
        meta_layout.addWidget(self.artist_label)

        info_layout.addWidget(self.artwork_badge)
        info_layout.addLayout(meta_layout)
        layout.addWidget(info_container)

        # Middle section: controls + timeline
        center_container = QWidget(self)
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(4)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(12)
        controls_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_prev = QPushButton("⏮")
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.clicked.connect(self.previous_clicked.emit)

        self.btn_play_pause = QPushButton("▶")
        self.btn_play_pause.setObjectName("btnPlayPause")
        self.btn_play_pause.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play_pause.clicked.connect(self.play_pause_clicked.emit)

        self.btn_next = QPushButton("⏭")
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.clicked.connect(self.next_clicked.emit)

        controls_layout.addWidget(self.btn_prev)
        controls_layout.addWidget(self.btn_play_pause)
        controls_layout.addWidget(self.btn_next)
        center_layout.addLayout(controls_layout)

        timeline_layout = QHBoxLayout()
        timeline_layout.setSpacing(8)

        self.pos_label = QLabel("00:00")
        self.pos_label.setStyleSheet("font-size: 11px; color: #7f91a4;")
        self.pos_label.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.sliderPressed.connect(self._on_slider_pressed)
        self.slider.sliderReleased.connect(self._on_slider_released)

        self.dur_label = QLabel("00:00")
        self.dur_label.setStyleSheet("font-size: 11px; color: #7f91a4;")
        self.dur_label.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        timeline_layout.addWidget(self.pos_label)
        timeline_layout.addWidget(self.slider)
        timeline_layout.addWidget(self.dur_label)
        center_layout.addLayout(timeline_layout)

        layout.addWidget(center_container, stretch=1)

        # Right section: extras (lyrics, info, speed, volume)
        right_container = QWidget(self)
        right_container.setFixedWidth(280)
        right_layout = QHBoxLayout(right_container)
        right_layout.setSpacing(8)

        self.btn_lyrics = QPushButton("📝")
        self.btn_lyrics.setObjectName("btnLyrics")
        self.btn_lyrics.setToolTip("متن آهنگ (Lyrics)")
        self.btn_lyrics.setEnabled(False)
        self.btn_lyrics.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_lyrics.clicked.connect(self.lyrics_clicked.emit)

        self.btn_info = QPushButton("ℹ️")
        self.btn_info.setObjectName("btnInfo")
        self.btn_info.setToolTip("مشخصات و متادیتا")
        self.btn_info.setEnabled(False)
        self.btn_info.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_info.clicked.connect(self.track_info_clicked.emit)

        self.btn_speed = QPushButton("1.0x")
        self.btn_speed.setObjectName("btnSpeed")
        self.btn_speed.setToolTip("سرعت پخش")
        self.btn_speed.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_speed.clicked.connect(self._open_speed_menu)

        vol_icon = QLabel("🔊")
        vol_icon.setStyleSheet("font-size: 14px;")

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
        """Capture mouse click on track info area (cover + title) to emit signal."""
        if obj == self.info_container and event.type() == QEvent.Type.MouseButtonPress:
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
            QMenu::item:selected {
                background-color: #2481cc;
            }
        """)

        for speed in SPEED_OPTIONS:
            label = f"{speed}x (عادی)" if speed == 1.0 else f"{speed}x"
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
        self.title_label.setText(track.display_title)
        self.artist_label.setText(track.display_artist)
        self.dur_label.setText(track.formatted_duration)
        self.btn_info.setEnabled(True)
        self.btn_lyrics.setEnabled(False)
        self.update_cover(track.cover_path)

    def reset_track(self) -> None:
        """Reset player bar to idle empty state when track is deleted/stopped."""
        self._current_track = None
        self._duration_ms = 0
        self.title_label.setText("آهنگی در حال پخش نیست")
        self.artist_label.setText("TMusic Desktop")
        self.dur_label.setText("00:00")
        self.pos_label.setText("00:00")
        self.slider.setValue(0)
        self.btn_play_pause.setText("▶")
        self.btn_lyrics.setEnabled(False)
        self.btn_info.setEnabled(False)
        self.artwork_badge.setPixmap(create_playerbar_cover_pixmap(size=48))

    def update_metadata(self, metadata: AudioMetadata) -> None:
        has_lyrics = metadata.has_lyrics
        self.btn_lyrics.setEnabled(has_lyrics)
        if has_lyrics:
            self.btn_lyrics.setToolTip("مشاهده متن آهنگ 📝 (موجود است)")
        else:
            self.btn_lyrics.setToolTip("متن آهنگ یافت نشد")

    def update_cover(self, cover_path: str | None) -> None:
        if self._current_track:
            pixmap = create_playerbar_cover_pixmap(
                minithumb_data=self._current_track.minithumbnail_data,
                cover_path=cover_path or self._current_track.cover_path,
                size=48,
            )
            self.artwork_badge.setPixmap(pixmap)

    def set_playback_state(self, is_playing: bool) -> None:
        self.btn_play_pause.setText("⏸" if is_playing else "▶")

    def set_position(self, position_ms: int) -> None:
        if not self._is_slider_dragging and self._duration_ms > 0:
            val = int((position_ms / self._duration_ms) * 1000)
            self.slider.setValue(val)

        sec = position_ms // 1000
        self.pos_label.setText(f"{sec // 60:02d}:{sec % 60:02d}")

    def set_duration(self, duration_ms: int) -> None:
        self._duration_ms = duration_ms
        sec = duration_ms // 1000
        self.dur_label.setText(f"{sec // 60:02d}:{sec % 60:02d}")

    def _on_slider_pressed(self) -> None:
        self._is_slider_dragging = True

    def _on_slider_released(self) -> None:
        self._is_slider_dragging = False
        if self._duration_ms > 0:
            target_ms = int((self.slider.value() / 1000.0) * self._duration_ms)
            self.seek_requested.emit(target_ms)