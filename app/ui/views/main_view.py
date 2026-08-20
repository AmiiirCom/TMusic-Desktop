import logging
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import AppConfig
from app.models.chat import OwnedChat
from app.models.track import Track
from app.models.user import TelegramUser
from app.settings.service import ProxySettings
from app.ui.components.player_bar import PlayerBar
from app.ui.components.sidebar import SidebarWidget
from app.ui.components.track_list_widget import TrackListWidget

logger = logging.getLogger("tmusic.ui.mainview")


class MainView(QWidget):
    """Main dashboard combining responsive sidebar, track library view, and bottom player bar."""

    chat_selected = Signal(OwnedChat)
    track_selected = Signal(Track)
    track_like_toggled = Signal(Track)
    load_more_tracks_requested = Signal(object)
    settings_requested = Signal()
    search_full_requested = Signal(str, str)
    chat_search_requested = Signal(str)

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._active_chat: OwnedChat | None = None
        self._original_tracks: list[Track] = []
        self._is_searching = False
        self._original_chats: list[OwnedChat] = []
        self._is_chat_searching = False
        self._connection_state = "connectionStateReady"
        self._proxy_settings = ProxySettings()
        self._current_retry_sec = 0

        self._init_ui()
        self._init_timers()

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        self.sidebar = SidebarWidget(self)
        self.sidebar.settings_requested.connect(self.settings_requested.emit)
        self.sidebar.chat_selected.connect(self._on_internal_chat_selected)
        self.sidebar.chat_search_input.textChanged.connect(self._on_chat_search_text_changed)

        content_area = QWidget(self)
        content_area.setStyleSheet("background-color: #0e1621;")
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.chat_header = QFrame(content_area)
        self.chat_header.setFixedHeight(68)
        self.chat_header.setStyleSheet("background-color: #17212b; border-bottom: 1px solid #0e1621;")
        header_layout = QHBoxLayout(self.chat_header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        header_layout.setSpacing(16)

        self.selected_chat_title = QLabel("پلی لیستی انتخاب نشده است")
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
        self.search_input.setClearButtonEnabled(True)
        self.search_input.hide()
        self.search_input.textChanged.connect(self._on_search_text_changed)

        header_layout.addWidget(self.selected_chat_title)
        header_layout.addStretch()
        header_layout.addWidget(self.search_input)
        content_layout.addWidget(self.chat_header)

        self.content_stack = QStackedWidget(content_area)

        self.placeholder_page = QWidget()
        ph_layout = QVBoxLayout(self.placeholder_page)
        ph_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_msg = QLabel("لطفاً یک پلی لیست از سایدبار انتخاب کنید تا موزیک‌های آن بارگذاری شوند 🎵")
        self.placeholder_msg.setStyleSheet("color: #7f91a4; font-size: 14px;")
        ph_layout.addWidget(self.placeholder_msg)
        self.content_stack.addWidget(self.placeholder_page)

        self.track_list = TrackListWidget(content_area)
        self.track_list.track_selected.connect(self.track_selected.emit)
        self.track_list.track_like_toggled.connect(self.track_like_toggled.emit)
        self.track_list.load_more_requested.connect(self._on_load_more_tracks)
        self.content_stack.addWidget(self.track_list)

        self.search_loading_page = QWidget()
        loading_layout = QVBoxLayout(self.search_loading_page)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.setSpacing(16)

        self.search_progress = QProgressBar()
        self.search_progress.setRange(0, 0)
        self.search_progress.setFixedWidth(200)
        self.search_progress.setFixedHeight(4)
        self.search_progress.setStyleSheet("""
            QProgressBar { background-color: #242f3d; border: none; border-radius: 2px; }
            QProgressBar::chunk { background-color: #2481cc; border-radius: 2px; }
        """)
        self.search_loading_label = QLabel("🔍 در حال جستجو...")
        self.search_loading_label.setStyleSheet("color: #7f91a4; font-size: 14px;")
        loading_layout.addWidget(self.search_progress)
        loading_layout.addWidget(self.search_loading_label)
        self.content_stack.addWidget(self.search_loading_page)

        content_layout.addWidget(self.content_stack)

        splitter.addWidget(content_area)
        splitter.addWidget(self.sidebar)
        splitter.setSizes([720, 280])
        root_layout.addWidget(splitter, stretch=1)

        self.player_bar = PlayerBar(self._config, self)
        root_layout.addWidget(self.player_bar)

    def _init_timers(self) -> None:
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(500)
        self._search_timer.timeout.connect(self._perform_full_search)

        self._chat_search_timer = QTimer(self)
        self._chat_search_timer.setSingleShot(True)
        self._chat_search_timer.setInterval(500)
        self._chat_search_timer.timeout.connect(self._perform_chat_search)

    def set_connection_state(self, state: str, proxy: ProxySettings | None = None) -> None:
        self._connection_state = state
        if proxy:
            self._proxy_settings = proxy
        is_proxy = (self._proxy_settings.mode != "DIRECT" and self._proxy_settings.enabled)
        self.sidebar.update_shield(self._connection_state, is_proxy, self._current_retry_sec)

    def set_retry_interval(self, interval_sec: int) -> None:
        self._current_retry_sec = interval_sec
        is_proxy = (self._proxy_settings.mode != "DIRECT" and self._proxy_settings.enabled)
        self.sidebar.update_shield(self._connection_state, is_proxy, self._current_retry_sec)

    def set_user(self, user: TelegramUser) -> None:
        self.sidebar.set_user(user)

    def set_owned_chats(self, chats: list[OwnedChat]) -> None:
        self.sidebar.chat_list.set_chats(chats)
        self._original_chats = list(chats)
        self.sidebar.chat_search_input.setVisible(bool(chats))

    def on_chat_search_results(self, chats: list[OwnedChat]) -> None:
        self.sidebar.chat_list.set_chats(chats)
        self._is_chat_searching = True

    def set_active_track(self, track: Track) -> None:
        self.track_list.set_active_track(track)

    def update_track_cover(self, track_id: str, cover_path: str) -> None:
        self.track_list.update_track_cover(track_id, cover_path)
        if self.player_bar._current_track and self.player_bar._current_track.id == track_id:
            self.player_bar.update_cover(cover_path)

    @Slot(object, object, bool, int)
    def update_track_reaction(self, chat_id: int, message_id: int, is_liked: bool, heart_count: int) -> None:
        self.track_list.update_track_reaction(chat_id, message_id, is_liked, heart_count)
        if self.player_bar._current_track and self.player_bar._current_track.id == f"{chat_id}_{message_id}":
            self.player_bar.update_reaction(is_liked, heart_count)

    def set_network_stats(self, speed_str: str, total_str: str) -> None:
        self.sidebar.net_stats_label.setText(f"⚡ {speed_str} | سشن: {total_str}")

    def scroll_to_track(self, track: Track) -> None:
        self.track_list.scroll_to_track(track.id)

    def on_full_search_results(self, chat_id: int, tracks: list[Track], has_more: bool) -> None:
        if not self._active_chat or self._active_chat.id != chat_id:
            return

        if not self._is_searching:
            self._original_tracks = list(self.track_list._all_tracks)
            self._is_searching = True

        if not tracks:
            self.placeholder_msg.setText("🔍 نتیجه‌ای برای جستجوی شما یافت نشد!")
            self.content_stack.setCurrentIndex(0)
        else:
            self.track_list.set_tracks(tracks, has_more=False)
            self.content_stack.setCurrentIndex(1)
            q = self.search_input.text().strip()
            if q:
                self.track_list.filter_tracks(q)

    def restore_normal_tracks(self) -> None:
        if self._is_searching and self._original_tracks:
            self.track_list.set_tracks(self._original_tracks, has_more=True)
            self.content_stack.setCurrentIndex(1)
            self._is_searching = False
            self._original_tracks = []
        elif not self._original_tracks:
            self.placeholder_msg.setText("هیچ موزیکی در این پلی لیست یافت نشد! 📂")
            self.content_stack.setCurrentIndex(0)

    def _on_internal_chat_selected(self, chat: OwnedChat) -> None:
        self._active_chat = chat
        self.selected_chat_title.setText(f"{chat.title} ({chat.type_display})")
        self.search_input.clear()
        self.search_input.show()
        self._search_timer.stop()
        self.placeholder_msg.setText("در حال دریافت ترک‌ها... 🔄")
        self.content_stack.setCurrentIndex(0)
        self.chat_selected.emit(chat)
        self._is_searching = False
        self._original_tracks = []
        self.sidebar.chat_list.set_active_chat(chat.id)

    def set_initial_tracks(self, tracks: list[Track], has_more: bool) -> None:
        if not tracks:
            self.placeholder_msg.setText("هیچ موزیکی در این پلی لیست یافت نشد! 📂")
            self.content_stack.setCurrentIndex(0)
            return
        self.track_list.set_tracks(tracks, has_more=has_more)
        self.content_stack.setCurrentIndex(1)
        self._original_tracks = list(tracks)
        self._is_searching = False

    def append_tracks(self, new_tracks: list[Track], has_more: bool) -> None:
        self.track_list.append_tracks(new_tracks, has_more=has_more)
        if not self._is_searching:
            self._original_tracks.extend(new_tracks)

    def prepend_tracks(self, new_tracks: list[Track]) -> None:
        self.track_list.prepend_tracks(new_tracks)
        if not self._is_searching:
            self._original_tracks = new_tracks + self._original_tracks

    def remove_tracks(self, chat_id: int, deleted_track_ids: list[str]) -> None:
        if self._active_chat and self._active_chat.id == chat_id:
            self.track_list.remove_tracks(deleted_track_ids)
            if not self._is_searching:
                del_set = set(deleted_track_ids)
                self._original_tracks = [t for t in self._original_tracks if t.id not in del_set]

    def _on_load_more_tracks(self) -> None:
        if self._active_chat:
            self.load_more_tracks_requested.emit(self._active_chat.id)

    def _on_search_text_changed(self, text: str) -> None:
        self._search_timer.stop()
        if not text.strip():
            self.restore_normal_tracks()
        else:
            self._search_timer.start()

    def _perform_full_search(self) -> None:
        query = self.search_input.text().strip()
        if self._active_chat and query:
            self.content_stack.setCurrentIndex(2)
            self.search_full_requested.emit(str(self._active_chat.id), query)

    def _on_chat_search_text_changed(self, text: str) -> None:
        self._chat_search_timer.stop()
        if not text.strip():
            if self._is_chat_searching and self._original_chats:
                self.sidebar.chat_list.set_chats(self._original_chats)
                self._is_chat_searching = False
        else:
            self._chat_search_timer.start()

    def _perform_chat_search(self) -> None:
        query = self.sidebar.chat_search_input.text().strip()
        if query:
            self.chat_search_requested.emit(query)
