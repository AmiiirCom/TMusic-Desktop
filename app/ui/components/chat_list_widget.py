from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.chat import OwnedChat

# Official Telegram Desktop vibrant avatar color palette
TELEGRAM_AVATAR_PALETTE: tuple[str, ...] = (
    "#e17076",  # Red / Coral
    "#faa774",  # Orange / Amber
    "#a695e7",  # Violet / Purple
    "#7bc862",  # Emerald Green
    "#6ec9cb",  # Cyan / Teal
    "#65aadd",  # Telegram Sky Blue
    "#ee7aae",  # Magenta / Pink
    "#f28935",  # Warm Orange
    "#56b949",  # Mint Green
    "#8e55e7",  # Deep Violet
)


def get_chat_avatar_color(chat_id: int) -> str:
    """Return a deterministic attractive color from Telegram palette for a given chat ID."""
    idx = abs(chat_id) % len(TELEGRAM_AVATAR_PALETTE)
    return TELEGRAM_AVATAR_PALETTE[idx]


def create_chat_avatar_pixmap(title: str, chat_id: int, size: int = 42) -> QPixmap:
    """Generate high-resolution anti-aliased circular avatar with initials and vibrant Telegram colors."""
    scale = 2
    render_size = size * scale
    pixmap = QPixmap(render_size, render_size)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    # Rounded circle clipping
    path = QPainterPath()
    path.addEllipse(0, 0, render_size, render_size)
    painter.setClipPath(path)

    # Fill vibrant background color
    bg_color = QColor(get_chat_avatar_color(chat_id))
    painter.fillRect(0, 0, render_size, render_size, bg_color)

    # Draw centered initial letter
    letter = title.strip()[:1].upper() if title.strip() else "C"
    painter.setPen(QColor("#ffffff"))
    font = QFont("Vazirmatn", 16 * scale, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, letter)

    painter.end()
    pixmap.setDevicePixelRatio(scale)
    return pixmap


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

        # Anti-aliased vibrant initial avatar
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(42, 42)
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_label.setPixmap(create_chat_avatar_pixmap(self.chat.title, self.chat.id, size=42))

        # Channel text info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(3)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        title_label = QLabel(self.chat.title)
        title_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold;")

        type_label = QLabel(f"🎵 {self.chat.type_display}")
        type_label.setStyleSheet("color: #7f91a4; font-size: 12px;")

        info_layout.addWidget(title_label)
        info_layout.addWidget(type_label)

        layout.addWidget(self.avatar_label)
        layout.addLayout(info_layout)
        layout.addStretch()


class OwnedChatListWidget(QListWidget):
    """List widget holding user owned music channels with search capability."""

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
        for i in range(self.count()):
            item = self.item(i)
            widget = self.itemWidget(item)
            if isinstance(widget, ChatItemWidget):
                is_active = (widget.chat.id == chat_id)
                item.setSelected(is_active)

    def update_chat_cover(self, chat_id: int, cover_path: str) -> None:
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