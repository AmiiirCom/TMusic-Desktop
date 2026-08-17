from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.models.chat import OwnedChat
from app.models.track import Track
from app.models.user import TelegramUser
from app.ui.components.chat_list_widget import OwnedChatListWidget
from app.ui.components.player_bar import PlayerBar
from app.ui.components.track_list_widget import TrackListWidget


class MainView(QWidget):
    """Telegram Desktop styled main dashboard view with lazy-loaded music library & player."""

    chat_selected = Signal(OwnedChat)
    track_selected = Signal(Track)
    load_more_tracks_requested = Signal(object)  # chat_id
    logout_requested = Signal()
    settings_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._active_chat: OwnedChat | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # 1. Sidebar Container
        sidebar = QWidget(self)
        sidebar.setFixedWidth(300)
        sidebar.setStyleSheet("background-color: #17212b; border-left: 1px solid #0e1621;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # User profile header
        user_header = QFrame(sidebar)
        user_header.setFixedHeight(64)
        user_header.setStyleSheet("background-color: #242f3d; padding: 8px 12px;")
        user_layout = QHBoxLayout(user_header)

        self.user_name_label = QLabel("کاربر تلگرام")
        self.user_name_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold;")

        btn_settings = QPushButton("⚙️")
        btn_settings.setToolTip("تنظیمات و حافظه")
        btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_settings.setStyleSheet("""
            QPushButton {
                background: #2f3e50;
                color: white;
                font-size: 14px;
                padding: 4px 8px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background: #3b4e64; }
        """)
        btn_settings.clicked.connect(self.settings_requested.emit)

        btn_logout = QPushButton("خروج")
        btn_logout.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_logout.setStyleSheet("""
            QPushButton {
                background: #e53935;
                color: white;
                font-size: 11px;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background: #d32f2f; }
        """)
        btn_logout.clicked.connect(self.logout_requested.emit)

        user_layout.addWidget(self.user_name_label)
        user_layout.addStretch()
        user_layout.addWidget(btn_settings)
        user_layout.addWidget(btn_logout)
        sidebar_layout.addWidget(user_header)

        # Section title
        section_label = QLabel("  کانال‌های موزیک شما")
        section_label.setFixedHeight(36)
        section_label.setStyleSheet("color: #6ab3f3; font-size: 12px; font-weight: bold;")
        sidebar_layout.addWidget(section_label)

        # Owned Chat List
        self.chat_list = OwnedChatListWidget(sidebar)
        self.chat_list.chat_selected.connect(self._on_internal_chat_selected)
        sidebar_layout.addWidget(self.chat_list, stretch=1)

        # Sidebar Bottom: Live Network Stats Bar
        stats_bar = QFrame(sidebar)
        stats_bar.setFixedHeight(32)
        stats_bar.setStyleSheet("background-color: #121921; padding: 4px 10px; border-top: 1px solid #0e1621;")
        stats_layout = QHBoxLayout(stats_bar)
        stats_layout.setContentsMargins(4, 0, 4, 0)

        self.net_stats_label = QLabel("⚡ دانلود: 0 KB/s | دیتای سشن: 0 KB")
        self.net_stats_label.setStyleSheet("color: #6ab3f3; font-size: 11px;")
        stats_layout.addWidget(self.net_stats_label)
        sidebar_layout.addWidget(stats_bar)

        # 2. Main Content Area
        content_area = QWidget(self)
        content_area.setStyleSheet("background-color: #0e1621;")
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Top Header Bar
        self.chat_header = QFrame(content_area)
        self.chat_header.setFixedHeight(64)
        self.chat_header.setStyleSheet("background-color: #17212b; border-bottom: 1px solid #0e1621;")
        header_layout = QHBoxLayout(self.chat_header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        header_layout.setSpacing(16)

        self.selected_chat_title = QLabel("کانالی انتخاب نشده است")
        self.selected_chat_title.setStyleSheet("color: #ffffff; font-size: 15px; font-weight: bold;")

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 جستجوی نام موزیک یا خواننده...")
        self.search_input.setFixedWidth(260)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #242f3d;
                border: 1px solid #2f3e50;
                border-radius: 16px;
                padding: 6px 14px;
                color: #ffffff;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #2481cc; }
        """)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.search_input.hide()

        header_layout.addWidget(self.selected_chat_title)
        header_layout.addStretch()
        header_layout.addWidget(self.search_input)
        content_layout.addWidget(self.chat_header)

        # Content Stack
        self.content_stack = QStackedWidget(content_area)

        # Page 0: Placeholder
        placeholder_page = QWidget()
        ph_layout = QVBoxLayout(placeholder_page)
        ph_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_msg = QLabel("لطفاً یک کانال یا گروه از سایدبار انتخاب کنید تا موزیک‌های آن بارگذاری شوند 🎵")
        self.placeholder_msg.setStyleSheet("color: #7f91a4; font-size: 14px;")
        ph_layout.addWidget(self.placeholder_msg)

        # Page 1: Track List
        self.track_list = TrackListWidget(content_area)
        self.track_list.track_selected.connect(self.track_selected.emit)
        self.track_list.load_more_requested.connect(self._on_load_more_tracks)

        self.content_stack.addWidget(placeholder_page)
        self.content_stack.addWidget(self.track_list)

        content_layout.addWidget(self.content_stack)

        splitter.addWidget(content_area)
        splitter.addWidget(sidebar)
        splitter.setSizes([720, 280])

        root_layout.addWidget(splitter, stretch=1)

        # 3. Bottom Player Bar
        self.player_bar = PlayerBar(self)
        root_layout.addWidget(self.player_bar)

    def set_user(self, user: TelegramUser) -> None:
        self.user_name_label.setText(user.full_name)

    def set_owned_chats(self, chats: list[OwnedChat]) -> None:
        self.chat_list.set_chats(chats)

    def set_active_track(self, track: Track) -> None:
        self.track_list.set_active_track(track)

    def set_network_stats(self, speed_str: str, total_str: str) -> None:
        self.net_stats_label.setText(f"⚡ {speed_str} | دیتای سشن: {total_str}")

    def _on_internal_chat_selected(self, chat: OwnedChat) -> None:
        self._active_chat = chat
        self.selected_chat_title.setText(f"{chat.title} ({chat.type_display})")
        self.search_input.clear()
        self.search_input.show()
        self.placeholder_msg.setText("در حال دریافت ترک‌ها... 🔄")
        self.content_stack.setCurrentIndex(0)
        self.chat_selected.emit(chat)

    def set_initial_tracks(self, tracks: list[Track], has_more: bool) -> None:
        if not tracks:
            self.placeholder_msg.setText("هیچ موزیکی در این کانال یافت نشد! 📂")
            self.content_stack.setCurrentIndex(0)
            return

        self.track_list.set_tracks(tracks, has_more=has_more)
        self.content_stack.setCurrentIndex(1)

    def append_tracks(self, new_tracks: list[Track], has_more: bool) -> None:
        self.track_list.append_tracks(new_tracks, has_more=has_more)

    def _on_load_more_tracks(self) -> None:
        if self._active_chat:
            self.load_more_tracks_requested.emit(self._active_chat.id)

    def _on_search_text_changed(self, text: str) -> None:
        self.track_list.filter_tracks(text)