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
    """List widget holding user owned music channels with search capability."""

    chat_selected = Signal(OwnedChat)
    search_requested = Signal(str)  # Emitted when user types a search query

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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_chats(self, chats: list[OwnedChat]) -> None:
        """Set the full list of chats and render them."""
        self._all_chats = list(chats)
        self._populate(self._all_chats)

    def filter_chats(self, query: str) -> None:
        self._current_query = query.strip().lower()

        if not self._current_query:
            self._populate(self._all_chats)
        else:
            filtered = [
                chat
                for chat in self._all_chats
                if self._current_query in chat.title.lower()
            ]
            self._populate(filtered)

        self.search_requested.emit(query.strip())

    def set_active_chat(self, chat_id: int | None) -> None:
        """Highlight the selected chat."""
        self._active_chat_id = chat_id
        # Update visual state of items
        for i in range(self.count()):
            item = self.item(i)
            widget = self.itemWidget(item)
            if isinstance(widget, ChatItemWidget):
                is_active = (widget.chat.id == chat_id)
                if is_active:
                    item.setSelected(True)
                else:
                    item.setSelected(False)

    def update_chat_cover(self, chat_id: int, cover_path: str) -> None:
        """Update cover for a specific chat (not used in chat list, kept for consistency)."""
        pass

    def scroll_to_chat(self, chat_id: int) -> None:
        """Scroll to a specific chat item."""
        for i in range(self.count()):
            item = self.item(i)
            widget = self.itemWidget(item)
            if isinstance(widget, ChatItemWidget) and widget.chat.id == chat_id:
                self.scrollToItem(item, QListWidget.ScrollHint.PositionAtCenter)
                break

    def restore_normal_chats(self) -> None:
        """Restore the original chat list (after search)."""
        self._populate(self._all_chats)
        self._current_query = ""

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

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