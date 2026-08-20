from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models.chat import OwnedChat
from app.models.user import TelegramUser
from app.ui.components.chat_list_widget import OwnedChatListWidget
from app.ui.utils.pixmaps import create_circular_avatar_pixmap, create_connection_shield_pixmap


class SidebarWidget(QWidget):
    """Telegram Desktop styled sidebar housing user profile, channel list, and network metrics."""

    settings_requested = Signal()
    chat_selected = Signal(OwnedChat)
    chat_search_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(300)
        self.setStyleSheet("background-color: #17212b; border-left: 1px solid #0e1621;")
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        user_header = QFrame(self)
        user_header.setObjectName("userHeader")
        user_header.setFixedHeight(68)
        user_header.setStyleSheet("""
            QFrame#userHeader {
                background-color: #242f3d;
                border-bottom: 1px solid #17212b;
            }
            QLabel#userAvatar { background: transparent; border: none; }
            QLabel#userName {
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
            QPushButton#btnHeaderAction {
                background-color: #17212b;
                color: #6ab3f3;
                font-size: 14px;
                padding: 6px 10px;
                border-radius: 6px;
                border: 1px solid #2f3e50;
            }
            QPushButton#btnHeaderAction:hover {
                background-color: #2b5278;
                color: #ffffff;
            }
        """)

        user_layout = QHBoxLayout(user_header)
        user_layout.setContentsMargins(14, 10, 14, 10)
        user_layout.setSpacing(10)
        user_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.user_avatar = QLabel()
        self.user_avatar.setObjectName("userAvatar")
        self.user_avatar.setFixedSize(42, 42)
        self.user_avatar.setPixmap(create_circular_avatar_pixmap(None, None, "U", 42))

        self.user_name_label = QLabel("کاربر تلگرام")
        self.user_name_label.setObjectName("userName")

        btn_settings = QPushButton("⚙️")
        btn_settings.setObjectName("btnHeaderAction")
        btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_settings.clicked.connect(self.settings_requested.emit)

        user_layout.addWidget(self.user_avatar)
        user_layout.addWidget(self.user_name_label, stretch=1)
        user_layout.addWidget(btn_settings)
        layout.addWidget(user_header)

        chat_search_container = QWidget(self)
        chat_search_container.setFixedHeight(44)
        chat_search_layout = QHBoxLayout(chat_search_container)
        chat_search_layout.setContentsMargins(10, 6, 10, 6)

        self.chat_search_input = QLineEdit()
        self.chat_search_input.setPlaceholderText("🔍 جستجوی کانال...")
        self.chat_search_input.setStyleSheet("""
            QLineEdit {
                background-color: #242f3d;
                border: 1px solid #2f3e50;
                border-radius: 12px;
                padding: 6px 12px;
                color: #ffffff;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #2481cc; }
        """)
        self.chat_search_input.setClearButtonEnabled(True)
        self.chat_search_input.hide()
        chat_search_layout.addWidget(self.chat_search_input)
        layout.addWidget(chat_search_container)

        section_label = QLabel("  کانال‌های موزیک شما")
        section_label.setFixedHeight(36)
        section_label.setStyleSheet("color: #6ab3f3; font-size: 12px; font-weight: bold;")
        layout.addWidget(section_label)

        self.chat_list = OwnedChatListWidget(self)
        self.chat_list.chat_selected.connect(self.chat_selected.emit)
        layout.addWidget(self.chat_list, stretch=1)

        stats_bar = QFrame(self)
        stats_bar.setFixedHeight(34)
        stats_bar.setStyleSheet("background-color: #121921; border-top: 1px solid #0e1621;")
        stats_layout = QHBoxLayout(stats_bar)
        stats_layout.setContentsMargins(8, 0, 10, 0)
        stats_layout.setSpacing(8)

        self.shield_badge = QLabel()
        self.shield_badge.setFixedSize(22, 22)
        self.shield_badge.setStyleSheet("background-color: transparent; border: none;")

        self.net_stats_label = QLabel("⚡ دانلود: 0 KB/s | سشن: 0 KB")
        self.net_stats_label.setStyleSheet("color: #6ab3f3; font-size: 11px;")

        stats_layout.addWidget(self.shield_badge)
        stats_layout.addWidget(self.net_stats_label, stretch=1)
        layout.addWidget(stats_bar)

    def set_user(self, user: TelegramUser) -> None:
        self.user_name_label.setText(user.full_name)
        self.user_avatar.setPixmap(
            create_circular_avatar_pixmap(user.photo_path, user.minithumb_data, user.initial_letter, 42)
        )

    def update_shield(self, state: str, is_proxy: bool, retry_sec: int = 0) -> None:
        status_key = "ready" if state == "connectionStateReady" else "waiting"
        self.shield_badge.setPixmap(create_connection_shield_pixmap(status_key, is_proxy))
