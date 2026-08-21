from typing import Any
from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
)
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.utils.icons import get_svg_icon


class BaseModalDialog(QDialog):
    """
    Full-window modal backdrop dialog with rounded-corner clipping
    synchronized with the main application window frame.
    """

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._is_closing = False
        self._fade_anim: QPropertyAnimation | None = None

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.card_frame = QFrame(self)
        self.card_frame.setObjectName("modalCardFrame")
        self.card_frame.setStyleSheet("""
            QFrame#modalCardFrame {
                background-color: #17212b;
                border: 1.5px solid #2f3e50;
                border-radius: 12px;
            }
            QLabel {
                color: #ffffff;
                font-family: 'Segoe UI', 'Vazirmatn', sans-serif;
            }
            QLineEdit, QComboBox {
                padding: 8px 12px;
                border: 1px solid #2f3e50;
                border-radius: 6px;
                background-color: #242f3d;
                color: #ffffff;
                font-size: 13px;
                min-height: 18px;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #2481cc;
            }
            QPushButton {
                background-color: #2481cc;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
                border: none;
                font-size: 13px;
                min-height: 18px;
            }
            QPushButton:hover { background-color: #1d72b8; }
            QPushButton#modalCloseBtn {
                background: transparent;
                border-radius: 14px;
                min-width: 28px;
                min-height: 28px;
                max-width: 28px;
                max-height: 28px;
                padding: 0px;
                border: none;
            }
            QPushButton#modalCloseBtn:hover {
                background-color: #e53935;
            }
        """)

        card_layout = QVBoxLayout(self.card_frame)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # Header Bar
        self.header_bar = QFrame(self.card_frame)
        self.header_bar.setFixedHeight(50)
        self.header_bar.setStyleSheet("border-bottom: 1px solid #242f3d;")
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(18, 0, 14, 0)

        self.modal_title = QLabel(title, self.header_bar)
        self.modal_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #6ab3f3;")

        self.btn_close_modal = QPushButton(self.header_bar)
        self.btn_close_modal.setObjectName("modalCloseBtn")
        self.btn_close_modal.setIcon(get_svg_icon("close", "#7f91a4", 16))
        self.btn_close_modal.setIconSize(QSize(16, 16))
        self.btn_close_modal.setToolTip(self.tr("Close"))
        self.btn_close_modal.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close_modal.clicked.connect(self.reject)

        header_layout.addWidget(self.modal_title)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_close_modal)
        card_layout.addWidget(self.header_bar)

        # Body Container
        self.content_widget = QWidget(self.card_frame)
        self.body_layout = QVBoxLayout(self.content_widget)
        self.body_layout.setContentsMargins(20, 16, 20, 20)
        self.body_layout.setSpacing(12)
        card_layout.addWidget(self.content_widget, stretch=1)

        root_layout.addWidget(self.card_frame)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)

    def paintEvent(self, event: Any) -> None:
        """Render anti-aliased backdrop with safe painter begin/end check."""
        painter = QPainter()
        if painter.begin(self):
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                parent = self.parentWidget()
                is_max = parent.window().isMaximized() if parent else False
                radius = 0.0 if is_max else 10.0

                path = QPainterPath()
                path.addRoundedRect(QRectF(self.rect()), radius, radius)
                painter.fillPath(path, QColor(0, 0, 0, 160))
            finally:
                painter.end()

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        parent = self.parentWidget()
        if parent:
            p_win = parent.window()
            g_pos = p_win.mapToGlobal(QPoint(0, 0))
            self.setGeometry(g_pos.x(), g_pos.y(), p_win.width(), p_win.height())

        self._is_closing = False
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.setDuration(160)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.start()

    def _finish_close(self, result_code: int) -> None:
        super().done(result_code)

    def reject(self) -> None:
        if self._is_closing:
            return
        self._is_closing = True

        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.setDuration(120)
        self._fade_anim.setStartValue(self._opacity_effect.opacity())
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_anim.finished.connect(lambda: self._finish_close(QDialog.DialogCode.Rejected))
        self._fade_anim.start()

    def accept(self) -> None:
        if self._is_closing:
            return
        self._is_closing = True

        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.setDuration(120)
        self._fade_anim.setStartValue(self._opacity_effect.opacity())
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_anim.finished.connect(lambda: self._finish_close(QDialog.DialogCode.Accepted))
        self._fade_anim.start()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        click_pos = event.position().toPoint()
        if not self.card_frame.geometry().contains(click_pos):
            self.reject()
        else:
            super().mousePressEvent(event)