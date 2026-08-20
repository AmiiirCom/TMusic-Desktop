from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.ui.utils.icons import get_svg_icon

SPEED_OPTIONS = (0.75, 1.0, 1.25, 1.5, 1.75)


class PlayerControls(QWidget):
    """Central playback buttons and seekable progress timeline with crisp SVG icons."""

    play_pause_clicked = Signal()
    next_clicked = Signal()
    previous_clicked = Signal()
    seek_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._duration_ms = 0
        self._is_dragging = False
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btns_layout = QHBoxLayout()
        btns_layout.setSpacing(12)
        btns_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_prev = QPushButton()
        self.btn_prev.setIcon(get_svg_icon("previous", "#ffffff", 18))
        self.btn_prev.setIconSize(QSize(18, 18))
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.clicked.connect(self.previous_clicked.emit)

        self.btn_play_pause = QPushButton()
        self.btn_play_pause.setObjectName("btnPlayPause")
        self.btn_play_pause.setIcon(get_svg_icon("play", "#ffffff", 18))
        self.btn_play_pause.setIconSize(QSize(18, 18))
        self.btn_play_pause.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play_pause.clicked.connect(self.play_pause_clicked.emit)

        self.btn_next = QPushButton()
        self.btn_next.setIcon(get_svg_icon("next", "#ffffff", 18))
        self.btn_next.setIconSize(QSize(18, 18))
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.clicked.connect(self.next_clicked.emit)

        btns_layout.addWidget(self.btn_prev)
        btns_layout.addWidget(self.btn_play_pause)
        btns_layout.addWidget(self.btn_next)
        layout.addLayout(btns_layout)

        timeline_layout = QHBoxLayout()
        timeline_layout.setSpacing(8)

        self.pos_label = QLabel("00:00")
        self.pos_label.setStyleSheet("font-size: 11px; color: #7f91a4;")

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.sliderPressed.connect(self._on_pressed)
        self.slider.sliderReleased.connect(self._on_released)

        self.dur_label = QLabel("00:00")
        self.dur_label.setStyleSheet("font-size: 11px; color: #7f91a4;")

        timeline_layout.addWidget(self.pos_label)
        timeline_layout.addWidget(self.slider)
        timeline_layout.addWidget(self.dur_label)
        layout.addLayout(timeline_layout)

    def set_playback_state(self, is_playing: bool) -> None:
        icon_name = "pause" if is_playing else "play"
        self.btn_play_pause.setIcon(get_svg_icon(icon_name, "#ffffff", 18))

    def set_position(self, pos_ms: int) -> None:
        if not self._is_dragging and self._duration_ms > 0:
            self.slider.setValue(int((pos_ms / self._duration_ms) * 1000))
        sec = pos_ms // 1000
        self.pos_label.setText(f"{sec // 60:02d}:{sec % 60:02d}")

    def set_duration(self, dur_ms: int) -> None:
        self._duration_ms = dur_ms
        sec = dur_ms // 1000
        self.dur_label.setText(f"{sec // 60:02d}:{sec % 60:02d}")

    def _on_pressed(self) -> None:
        self._is_dragging = True

    def _on_released(self) -> None:
        self._is_dragging = False
        if self._duration_ms > 0:
            target = int((self.slider.value() / 1000.0) * self._duration_ms)
            self.seek_requested.emit(target)