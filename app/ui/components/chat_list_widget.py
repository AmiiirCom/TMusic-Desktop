from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.chat import OwnedChat, get_favorites_chat
from app.ui.utils.pixmaps import create_chat_avatar_pixmap


class ChatItemWidget(QWidget):
    """Custom Telegram-style channel list item widget with vibrant avatars."""

    def __init__(self, chat: OwnedChat, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.chat = chat
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(12)

        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(42, 42)
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_label.setPixmap(create_chat_avatar_pixmap(self.chat.title, self.chat.id, size=42))

        info_layout = QVBoxLayout()
        info_layout.setSpacing(3)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        title_label = QLabel(self.chat.title)
        title_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold;")

        icon_prefix = "❤️" if self.chat.is_favorites else "🎵"
        type_label = QLabel(f"{icon_prefix} {self.chat.type_display}")
        type_label.setStyleSheet("color: #7f91a4; font-size: 12px;")

        info_layout.addWidget(title_label)
        info_layout.addWidget(type_label)

        layout.addWidget(self.avatar_label)
        layout.addLayout(info_layout)
        layout.addStretch()


class OwnedChatListWidget(QListWidget):
    """List widget holding user owned music channels with pinned Favorites entry."""

    chat_selected = Signal(OwnedChat)
    search_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._all_chats: list[OwnedChat] = []
        self._current_query: str = ""
        self._chat_widgets: dict[int, ChatItemWidget] = {}
        self._active_chat_id: int | None = None

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
        """Set the full list of chats, always keeping Favorites pinned at the top."""
        favorites_chat = get_favorites_chat()
        other_chats = [c for c in chats if not c.is_favorites]
        self._all_chats = [favorites_chat] + other_chats
        self._populate(self._all_chats)

    def filter_chats(self, query: str) -> None:
        self._current_query = query.strip().lower()

        if not self._current_query:
            self._populate(self._all_chats)
        else:
            filtered = [
                chat
                for chat in self._all_chats
                if self._current_query in chat.title.lower() or chat.is_favorites
            ]
            self._populate(filtered)

        self.search_requested.emit(query.strip())

    def set_active_chat(self, chat_id: int | None) -> None:
        self._active_chat_id = chat_id
        for i in range(self.count()):
            item = self.item(i)
            widget = self.itemWidget(item)
            if isinstance(widget, ChatItemWidget):
                is_active = (widget.chat.id == chat_id)
                item.setSelected(is_active)

    def _populate(self, chats: list[OwnedChat]) -> None:
        self.clear()
        self._chat_widgets.clear()
        for chat in chats:
            item = QListWidgetItem(self)
            widget = ChatItemWidget(chat)
            item.setSizeHint(widget.sizeHint())
            self.addItem(item)
            self.setItemWidget(item, widget)
            self._chat_widgets[chat.id] = widget

            if self._active_chat_id == chat.id:
                item.setSelected(True)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        widget = self.itemWidget(item)
        if isinstance(widget, ChatItemWidget):
            self.chat_selected.emit(widget.chat)
            self.set_active_chat(widget.chat.id)