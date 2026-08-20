from typing import Any
from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.utils.icons import get_svg_icon


class BaseModalDialog(QDialog):
    """Full-window modal backdrop dialog with vector SVG close button."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
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

        self.modal_title = QLabel(title)
        self.modal_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #6ab3f3;")

        self.btn_close_modal = QPushButton()
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

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 160))
        painter.end()

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        parent = self.parentWidget()
        if parent:
            p_win = parent.window()
            g_pos = p_win.mapToGlobal(QPoint(0, 0))
            self.setGeometry(g_pos.x(), g_pos.y(), p_win.width(), p_win.height())

    def mousePressEvent(self, event: QMouseEvent) -> None:
        click_pos = event.position().toPoint()
        if not self.card_frame.geometry().contains(click_pos):
            self.reject()
        else:
            super().mousePressEvent(event)