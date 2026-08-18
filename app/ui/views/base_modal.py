from typing import Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class BaseModalDialog(QDialog):
    """Frameless, centered, uniform modal dialog with Telegram-style topbar and close button."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        # Main Card Frame
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
                font-family: 'Vazirmatn', 'Segoe UI', sans-serif;
            }
            QLineEdit, QComboBox {
                padding: 6px 10px;
                border: 1px solid #2f3e50;
                border-radius: 6px;
                background-color: #242f3d;
                color: #ffffff;
                font-size: 13px;
            }
            QPushButton {
                background-color: #2481cc;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #1d72b8; }
            QPushButton#modalCloseBtn {
                background: transparent;
                color: #7f91a4;
                font-size: 15px;
                font-weight: bold;
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
                color: #ffffff;
            }
        """)

        card_layout = QVBoxLayout(self.card_frame)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # 1. Custom Header Bar (Title + Uniform Close Icon ✕)
        self.header_bar = QFrame(self.card_frame)
        self.header_bar.setFixedHeight(50)
        self.header_bar.setStyleSheet("border-bottom: 1px solid #242f3d;")
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(18, 0, 14, 0)

        self.modal_title = QLabel(title)
        self.modal_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #6ab3f3;")

        self.btn_close_modal = QPushButton("✕")
        self.btn_close_modal.setObjectName("modalCloseBtn")
        self.btn_close_modal.setToolTip("بستن (Esc)")
        self.btn_close_modal.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close_modal.clicked.connect(self.reject)

        header_layout.addWidget(self.modal_title)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_close_modal)
        card_layout.addWidget(self.header_bar)

        # 2. Content Body Area
        self.content_widget = QWidget(self.card_frame)
        self.body_layout = QVBoxLayout(self.content_widget)
        self.body_layout.setContentsMargins(22, 18, 22, 22)
        self.body_layout.setSpacing(14)
        card_layout.addWidget(self.content_widget, stretch=1)

        root_layout.addWidget(self.card_frame)

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        self._center_on_parent()

    def _center_on_parent(self) -> None:
        """Position dialog precisely in the center of its parent window."""
        parent = self.parentWidget()
        if parent:
            parent_geo = parent.geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
            self.move(max(0, x), max(0, y))