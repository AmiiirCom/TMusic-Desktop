from enum import IntEnum
import re
import time
from typing import Any
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

# Match Persian, Arabic, and Hebrew Unicode directional character ranges
RTL_CHAR_REGEX = re.compile(r"[\u0591-\u07FF\uFB1D-\uFDFD\uFE70-\uFEFC]")


def is_rtl_text(text: str) -> bool:
    """Determine whether text direction is predominantly Right-to-Left (Persian/Arabic)."""
    for ch in text:
        if RTL_CHAR_REGEX.match(ch):
            return True
        if ch.isascii() and ch.isalpha():
            return False
    return False


class MarqueeState(IntEnum):
    IDLE = 0
    PAUSE_START = 1
    SCROLLING_FORWARD = 2
    PAUSE_END = 3
    SCROLLING_BACKWARD = 4


class MarqueeLabel(QWidget):
    """
    Ultra-smooth, zero-allocation 60fps auto-sliding text label with safe painter instantiation,
    positive point size font handling, and edge-fading alpha gradient masks.
    """

    def __init__(
        self,
        text: str = "",
        fade_width: int = 18,
        speed_px_per_sec: float = 32.0,
        pause_sec: float = 1.5,
        alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._fade_width = fade_width
        self._speed = speed_px_per_sec
        self._pause_duration = pause_sec
        self._text_color = QColor("#ffffff")
        self._is_rtl = is_rtl_text(text)
        self._alignment = alignment

        # Explicit positive point size font
        init_font = QFont("Segoe UI")
        init_font.setPointSize(10)
        self.setFont(init_font)

        self._offset: float = 0.0
        self._state = MarqueeState.IDLE
        self._state_start_time: float = 0.0
        self._last_tick_time: float = 0.0

        # Persistent reusable render buffers
        self._buffer_pixmap: QPixmap | None = None
        self._left_gradient: QLinearGradient | None = None
        self._right_gradient: QLinearGradient | None = None

        # Precision 60 FPS animation timer (16ms interval)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._on_animation_tick)

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent; background-color: transparent; border: none;")

    def setText(self, text: str) -> None:
        if self._text == text:
            return
        self._text = text
        self._is_rtl = is_rtl_text(text)
        self._offset = 0.0
        self._reset_and_start()
        self.update()

    def text(self) -> str:
        return self._text

    def setTextColor(self, color: QColor | str) -> None:
        self._text_color = QColor(color)
        self.update()

    def setAlignment(self, alignment: Qt.AlignmentFlag) -> None:
        self._alignment = alignment
        self.update()

    def alignment(self) -> Qt.AlignmentFlag:
        return self._alignment

    def _reset_and_start(self) -> None:
        if not self._text or self.width() <= 0:
            self._timer.stop()
            self._state = MarqueeState.IDLE
            self._offset = 0.0
            return

        fm = QFontMetrics(self.font())
        text_width = fm.horizontalAdvance(self._text)
        avail_width = self.width()

        if text_width <= avail_width:
            self._timer.stop()
            self._state = MarqueeState.IDLE
            self._offset = 0.0
            return

        now = time.perf_counter()
        self._state = MarqueeState.PAUSE_START
        self._state_start_time = now
        self._last_tick_time = now
        self._offset = 0.0

        if not self._timer.isActive():
            self._timer.start()

    def _on_animation_tick(self) -> None:
        if not self.isVisible() or not self._text or self.width() <= 0:
            return

        now = time.perf_counter()
        dt = now - self._last_tick_time
        self._last_tick_time = now
        dt = min(dt, 0.05)

        fm = QFontMetrics(self.font())
        text_width = fm.horizontalAdvance(self._text)
        avail_width = self.width()
        overflow = max(0.0, float(text_width - avail_width + self._fade_width))

        if overflow <= 0.0:
            self._timer.stop()
            self._state = MarqueeState.IDLE
            self._offset = 0.0
            self.update()
            return

        if self._state == MarqueeState.PAUSE_START:
            if now - self._state_start_time >= self._pause_duration:
                self._state = MarqueeState.SCROLLING_FORWARD

        elif self._state == MarqueeState.SCROLLING_FORWARD:
            self._offset += self._speed * dt
            if self._offset >= overflow:
                self._offset = overflow
                self._state = MarqueeState.PAUSE_END
                self._state_start_time = now
            self.update()

        elif self._state == MarqueeState.PAUSE_END:
            if now - self._state_start_time >= self._pause_duration:
                self._state = MarqueeState.SCROLLING_BACKWARD

        elif self._state == MarqueeState.SCROLLING_BACKWARD:
            self._offset -= self._speed * dt
            if self._offset <= 0.0:
                self._offset = 0.0
                self._state = MarqueeState.PAUSE_START
                self._state_start_time = now
            self.update()

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        w = self.width()
        h = self.height()
        if w > 0 and h > 0:
            self._rebuild_gradients(w, h)
            self._buffer_pixmap = None
        self._reset_and_start()

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        self._reset_and_start()

    def _rebuild_gradients(self, w: int, h: int) -> None:
        self._left_gradient = QLinearGradient(0, 0, self._fade_width, 0)
        self._left_gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        self._left_gradient.setColorAt(1.0, QColor(0, 0, 0, 255))

        self._right_gradient = QLinearGradient(w - self._fade_width, 0, w, 0)
        self._right_gradient.setColorAt(0.0, QColor(0, 0, 0, 255))
        self._right_gradient.setColorAt(1.0, QColor(0, 0, 0, 0))

    def paintEvent(self, event: Any) -> None:
        if not self._text:
            return

        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return

        fm = QFontMetrics(self.font())
        text_width = fm.horizontalAdvance(self._text)
        is_overflowing = text_width > w

        # 1. Non-overflowing static text with safe painter check
        if not is_overflowing:
            painter = QPainter()
            if painter.begin(self):
                try:
                    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
                    painter.setFont(self.font())
                    painter.setPen(self._text_color)
                    painter.drawText(self.rect(), self._alignment, self._text)
                finally:
                    painter.end()
            return

        # 2. Overflowing text: render through reusable offscreen buffer
        scale = self.devicePixelRatio()
        buf_w = max(1, int(w * scale))
        buf_h = max(1, int(h * scale))

        if (
            self._buffer_pixmap is None
            or self._buffer_pixmap.width() != buf_w
            or self._buffer_pixmap.height() != buf_h
        ):
            self._buffer_pixmap = QPixmap(buf_w, buf_h)
            self._buffer_pixmap.setDevicePixelRatio(scale)
            if not self._left_gradient or not self._right_gradient:
                self._rebuild_gradients(w, h)

        self._buffer_pixmap.fill(Qt.GlobalColor.transparent)

        buf_painter = QPainter()
        if buf_painter.begin(self._buffer_pixmap):
            try:
                buf_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                buf_painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
                buf_painter.setFont(self.font())
                buf_painter.setPen(self._text_color)

                y = (h - fm.height()) // 2 + fm.ascent()

                if not self._is_rtl:
                    x = (self._fade_width // 2) - self._offset
                else:
                    x = (w - text_width - (self._fade_width // 2)) + self._offset

                buf_painter.drawText(int(x), y, self._text)

                buf_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
                if self._left_gradient:
                    buf_painter.fillRect(0, 0, self._fade_width, h, self._left_gradient)
                if self._right_gradient:
                    buf_painter.fillRect(w - self._fade_width, 0, self._fade_width, h, self._right_gradient)
            finally:
                buf_painter.end()

        # Blit buffer with safe painter check
        painter = QPainter()
        if painter.begin(self):
            try:
                painter.drawPixmap(0, 0, self._buffer_pixmap)
            finally:
                painter.end()