from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.chat import OwnedChat


class ChatItemWidget(QWidget):
    """Custom Telegram-style channel list item widget."""

    def __init__(self, chat: OwnedChat, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.chat = chat
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(12)

        # Avatar circle with initial letter
        avatar = QLabel(self.chat.title[:1].upper() if self.chat.title else "C")
        avatar.setFixedSize(42, 42)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet("""
            QLabel {
                background-color: #2b5278;
                color: #ffffff;
                font-size: 16px;
                font-weight: bold;
                border-radius: 21px;
            }
        """)

        # Details
        info_layout = QVBoxLayout()
        info_layout.setSpacing(3)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        title_label = QLabel(self.chat.title)
        title_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold;")

        type_label = QLabel(f"🎵 {self.chat.type_display}")
        type_label.setStyleSheet("color: #7f91a4; font-size: 12px;")

        info_layout.addWidget(title_label)
        info_layout.addWidget(type_label)

        layout.addWidget(avatar)
        layout.addLayout(info_layout)
        layout.addStretch()


class OwnedChatListWidget(QListWidget):
    """List widget holding user owned music channels."""

    chat_selected = Signal(OwnedChat)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setStyleSheet("""
            QListWidget {
                background-color: #17212b;
                border: none;
                outline: none;
            }
            QListWidget::item {
                border-radius: 8px;
                margin: 2px 8px;
                background-color: transparent;
            }
            QListWidget::item:hover {
                background-color: #202b36;
            }
            QListWidget::item:selected {
                background-color: #2b5278;
            }
        """)
        self.itemClicked.connect(self._on_item_clicked)

    def set_chats(self, chats: list[OwnedChat]) -> None:
        self.clear()
        for chat in chats:
            item = QListWidgetItem(self)
            widget = ChatItemWidget(chat)
            item.setSizeHint(widget.sizeHint())
            self.addItem(item)
            self.setItemWidget(item, widget)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        widget = self.itemWidget(item)
        if isinstance(widget, ChatItemWidget):
            self.chat_selected.emit(widget.chat)