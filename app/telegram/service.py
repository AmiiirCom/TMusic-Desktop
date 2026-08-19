import base64
from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any
from PySide6.QtCore import QObject, QTimer, Signal

from app.config import AppConfig
from app.core.keywords import is_music_title
from app.models.chat import OwnedChat
from app.models.track import Track
from app.models.user import TelegramUser
from app.settings.service import SettingsService
from app.telegram.adapter import TDLibAdapter
from app.telegram.auth_handler import AuthHandler
from app.telegram.chat_handler import ChatHandler
from app.telegram.enums import AuthState
from app.telegram.media_handler import MediaHandler
from app.telegram.track_handler import TrackHandler
from app.telegram.worker import TDLibWorker

logger = logging.getLogger("tmusic.telegram.service")

@dataclass(slots=True)
class ChatTrackPaginationState:
    chat_id: int
    tracks: list[Track] = field(default_factory=list)
    next_from_message_id: int = 0
    is_loading: bool = False
    has_more: bool = True

class TelegramService(QObject):
    """Event-Driven Telegram service with direct header byte inspection and real-time updates."""

    auth_state_changed = Signal(str)
    auth_error = Signal(str)
    connection_state_changed = Signal(str)

    user_loaded = Signal(TelegramUser)
    owned_chats_loaded = Signal(list)
    chat_selected = Signal(object)

    tracks_loaded = Signal(object, list, bool)
    tracks_appended = Signal(object, list, bool)
    tracks_prepended = Signal(object, list)
    tracks_deleted = Signal(object, list)
    cover_downloaded = Signal(str, str)

    file_download_progress = Signal(int, int, int)
    file_download_completed = Signal(int, str)
    network_traffic_received = Signal(int, int)

    def __init__(
        self,
        config: AppConfig,
        adapter: TDLibAdapter,
        settings_service: SettingsService | None = None,
        cache_manager: Any = None,  # CacheManager
    ) -> None:
        super().__init__()
        self._config = config
        self._adapter = adapter
        self._settings = settings_service
        self._cache = cache_manager
        self._worker: TDLibWorker | None = None

        self._my_user_id: int = 0
        self._current_user: TelegramUser | None = None
        self._avatar_file_id: int = 0

        # 1. Initialize Event Handlers
        self._auth = AuthHandler(
            config=self._config,
            adapter=self._adapter,
            on_auth_state_changed=self._on_auth_state_changed,
            on_auth_ready=self._on_auth_ready,
            on_auth_closed=self._on_auth_closed,
        )

        self._media = MediaHandler(
            adapter=self._adapter,
            config=self._config,
            cache_manager=self._cache,
            on_audio_progress=self.file_download_progress.emit,
            on_audio_completed=self.file_download_completed.emit,
            on_cover_completed=self.cover_downloaded.emit,
        )

        self._chats = ChatHandler(
            adapter=self._adapter,
            settings_service=self._settings,
            on_owned_chats_updated=self.owned_chats_loaded.emit,
        )

        self._tracks = TrackHandler(
            adapter=self._adapter,
            request_cover_download=self._media.download_cover_file,
            register_file_path=self._media.register_completed_path,
            on_initial_chunk_loaded=self.tracks_loaded.emit,
            on_lazy_chunk_appended=self.tracks_appended.emit,
            on_delta_tracks_prepended=self.tracks_prepended.emit,
            on_tracks_deleted=self.tracks_deleted.emit,
        )

        # 2. Network Stats Poller Timer
        self._net_timer = QTimer(self)
        self._net_timer.setInterval(1000)
        self._net_timer.timeout.connect(self._poll_network_statistics)

    @property
    def current_user(self) -> TelegramUser | None:
        return self._current_user

    @property
    def current_auth_state(self) -> AuthState:
        return self._auth.current_state

    def set_settings_service(self, settings_service: SettingsService) -> None:
        self._settings = settings_service
        self._chats.set_settings_service(settings_service)

    def set_online_status(self, is_online: bool) -> None:
        if self._adapter.is_loaded:
            self._adapter.send({
                "@type": "setOption",
                "name": "online",
                "value": {"@type": "optionValueBoolean", "value": is_online},
            })

    def set_network_monitor_active(self, is_active: bool) -> None:
        if is_active:
            if not self._net_timer.isActive():
                self._net_timer.start()
        else:
            if not self._media.has_active_downloads:
                self._net_timer.stop()

    def load_cached_state(self) -> None:
        self._chats.load_cached_chats()
        if self._settings:
            cached_user = self._settings.get_cached_user_profile()
            if cached_user:
                self._current_user = cached_user
                self._my_user_id = cached_user.id
                self.user_loaded.emit(cached_user)

    def get_downloaded_path(self, file_id: int) -> str | None:
        return self._media.get_downloaded_path(file_id)

    def register_downloaded_path(self, file_id: int, path: str) -> None:
        self._media.register_completed_path(file_id, path)

    def get_file_header_bytes(self, file_id: int, size: int = 131072) -> bytes | None:
        """Fetch initial header bytes from TDLib cache to parse embedded ID3 lyrics and tags."""
        if not self._adapter.is_loaded:
            return None
        res = self._adapter.request_sync({
            "@type": "readFilePart",
            "file_id": file_id,
            "offset": 0,
            "count": size,
        }, timeout=0.5)
        if res and res.get("@type") == "data":
            data_b64 = res.get("data", "")
            if data_b64:
                try:
                    return base64.b64decode(data_b64)
                except Exception:
                    pass
        return None

    def start(self) -> None:
        if not self._adapter.is_loaded:
            logger.error("Cannot start TelegramService: TDLib is not loaded")
            self.auth_error.emit("TDLib binary is missing or failed to load.")
            return

        self._worker = TDLibWorker(self._adapter)
        self._worker.update_received.connect(self._handle_update)
        self._worker.start()
        logger.info("TelegramService started")

    def _poll_network_statistics(self) -> None:
        if self._adapter.is_loaded:
            self._adapter.send({
                "@type": "getNetworkStatistics",
                "only_current": False,
                "@extra": "periodic_net_stats",
            })

    def _handle_update(self, update: dict[str, Any]) -> None:
        update_type = update.get("@type", "")
        extra = update.get("@extra", "")

        # A. Network Stats
        if extra == "periodic_net_stats" and update_type == "networkStatistics":
            total_rx = sum(e.get("received_bytes", 0) for e in update.get("entries", []))
            total_tx = sum(e.get("sent_bytes", 0) for e in update.get("entries", []))
            self.network_traffic_received.emit(total_rx, total_tx)
            return

        # B. Track Search Responses
        if isinstance(extra, str) and extra.startswith("load_tracks_"):
            parts = extra.split("_")
            chat_id = int(parts[2])
            is_initial = parts[3] == "initial"
            if update_type in ("foundChatMessages", "messages"):
                messages = update.get("messages", [])
                next_from_id = update.get("next_from_message_id", 0)
                self._tracks.process_search_response(chat_id, messages, next_from_id, is_initial)
            elif update_type == "error" and is_initial:
                self.tracks_loaded.emit(chat_id, [], False)
            return

        # C. Chat Pagination
        if extra in ("load_main_chats", "load_archive_chats"):
            self._chats.handle_pagination_response(extra, update_type)
            return

        # D. Supergroup Ownership Queries
        if isinstance(extra, str) and extra.startswith("check_supergroup_") and update_type == "supergroup":
            self._chats.process_supergroup_update(update)
            return

        # E. PURE REAL-TIME EVENT STREAM
        match update_type:
            case "updateAuthorizationState":
                self._auth.process_update(update.get("authorization_state", {}))

            case "updateConnectionState":
                state = update.get("state", {}).get("@type", "")
                self.connection_state_changed.emit(state)

            case "updateNewMessage":
                self._tracks.process_new_message(update.get("message", {}))

            case "updateDeleteMessages":
                is_permanent = update.get("is_permanent", True)
                from_cache = update.get("from_cache", False)
                if is_permanent and not from_cache:
                    chat_id = update.get("chat_id", 0)
                    message_ids = update.get("message_ids", [])
                    self._tracks.process_delete_messages(chat_id, message_ids)

            case "updateFile":
                file_obj = update.get("file", {})
                file_id = file_obj.get("id", 0)
                local = file_obj.get("local", {})
                if local.get("is_downloading_completed") and local.get("path"):
                    if file_id == self._avatar_file_id and self._current_user:
                        original_path = Path(local.get("path"))
                        if original_path.exists():
                            from app.core.image_compressor import compress_image, get_compressed_image_path
                            compressed_path = get_compressed_image_path(
                                self._config.thumb_cache_dir,
                                "avatar",
                                str(self._current_user.id)
                            )
                            result = compress_image(original_path, compressed_path)
                            if result:
                                self._current_user = TelegramUser(
                                    id=self._current_user.id,
                                    first_name=self._current_user.first_name,
                                    last_name=self._current_user.last_name,
                                    username=self._current_user.username,
                                    phone_number=self._current_user.phone_number,
                                    photo_id=self._current_user.photo_id,
                                    photo_file_id=self._avatar_file_id,
                                    photo_path=str(result),
                                    minithumb_data=self._current_user.minithumb_data,
                                )
                                if self._settings:
                                    self._settings.set_cached_user_profile(self._current_user)
                                self.user_loaded.emit(self._current_user)
                                # Delete original
                                try:
                                    original_path.unlink(missing_ok=True)
                                except Exception:
                                    pass

                    self._media.process_file_update(file_obj)

            case "user":
                self._extract_user(update, is_self=True)

            case "updateUser":
                user_obj = update.get("user", {})
                user_id = user_obj.get("id", 0)
                if self._my_user_id == 0 or user_id == self._my_user_id:
                    self._extract_user(user_obj, is_self=True)

            case "chats":
                for cid in update.get("chat_ids", []):
                    self._adapter.send({"@type": "getChat", "chat_id": cid})

            case "updateNewChat":
                self._chats.process_new_chat(update.get("chat", {}))

            case "updateSupergroup":
                self._chats.process_supergroup_update(update.get("supergroup", {}))

            case "updateBasicGroup":
                self._chats.process_basic_group_update(update.get("basic_group", {}))

            case "updateChatTitle":
                self._chats.process_chat_title_update(update.get("chat_id", 0), update.get("title", ""))

            case "error":
                code = update.get("code")
                msg = update.get("message", "")
                transient_msgs = (
                    "There is not enough downloaded bytes",
                    "Failed to read the file",
                )
                if code != 404 and not any(t in msg for t in transient_msgs):
                    logger.warning("TDLib Error: %s (code: %s)", msg, code)

    def _on_auth_state_changed(self, state: AuthState) -> None:
        self.auth_state_changed.emit(state.value)

    def _on_auth_ready(self) -> None:
        self.set_online_status(True)
        self._chats.start_chat_sync()

    def _on_auth_closed(self) -> None:
        logger.info("TDLib closed. Recreating fresh TDLib client instance...")
        self._net_timer.stop()
        if self._worker:
            self._worker.stop()

        self._my_user_id = 0
        self._current_user = None
        self._avatar_file_id = 0

        self._adapter.recreate_client()
        self._worker = TDLibWorker(self._adapter)
        self._worker.update_received.connect(self._handle_update)
        self._worker.start()

    def _extract_user(self, user_obj: dict[str, Any], is_self: bool = False) -> None:
        user_id = user_obj.get("id", 0)
        if not user_id:
            return

        if not is_self and self._my_user_id != 0 and user_id != self._my_user_id:
            return

        self._my_user_id = user_id

        usernames = user_obj.get("usernames", {})
        active_usernames = usernames.get("active_usernames", [])
        username = active_usernames[0] if active_usernames else user_obj.get("username", "")

        photo = user_obj.get("profile_photo", {})
        photo_id = photo.get("id", 0)

        big_file = photo.get("big", {}) if photo else {}
        small_file = photo.get("small", {}) if photo else {}
        target_photo_file = big_file if big_file.get("id") else small_file

        photo_file_id = target_photo_file.get("id", 0)
        photo_local = target_photo_file.get("local", {}) if target_photo_file else {}
        photo_path = photo_local.get("path") if photo_local.get("is_downloading_completed") else None

        minithumb = photo.get("minithumbnail") if photo else None
        minithumb_data = None
        if minithumb and "data" in minithumb:
            try:
                minithumb_data = base64.b64decode(minithumb["data"])
            except Exception:
                minithumb_data = None

        cached_user = self._settings.get_cached_user_profile() if self._settings else None
        is_same_photo = (
            cached_user
            and str(cached_user.photo_id) == str(photo_id)
            and cached_user.photo_path
            and Path(cached_user.photo_path).exists()
        )

        if is_same_photo and cached_user:
            photo_path = cached_user.photo_path
        elif photo_file_id > 0 and not photo_path:
            self._avatar_file_id = photo_file_id
            self._adapter.send({
                "@type": "downloadFile",
                "file_id": photo_file_id,
                "priority": 16,
                "offset": 0,
                "limit": 0,
                "synchronous": False,
            })

        user = TelegramUser(
            id=user_id,
            first_name=user_obj.get("first_name", ""),
            last_name=user_obj.get("last_name", ""),
            username=username,
            phone_number=user_obj.get("phone_number", ""),
            photo_id=photo_id,
            photo_file_id=photo_file_id,
            photo_path=photo_path,
            minithumb_data=minithumb_data,
        )

        self._current_user = user
        if self._settings:
            self._settings.set_cached_user_profile(user)

        self.user_loaded.emit(user)

    # --- Public Methods ---

    def send_phone_number(self, phone_number: str) -> None:
        self._auth.send_phone_number(phone_number)

    def send_code(self, code: str) -> None:
        self._auth.send_code(code)

    def send_password(self, password: str) -> None:
        self._auth.send_password(password)

    def download_file(self, file_id: int) -> None:
        self.set_network_monitor_active(True)
        self._media.download_audio_file(file_id)

    def prefetch_audio_file(self, file_id: int) -> None:
        self.set_network_monitor_active(True)
        self._media.prefetch_audio_file(file_id)

    def prefetch_cover_file(self, track_id: str, file_id: int) -> None:
        self._media.download_cover_file(track_id, file_id)

    def load_chat_tracks(self, chat_id: int, reset: bool = True, chunk_size: int = 40) -> None:
        self._tracks.load_chat_tracks(chat_id, reset=reset, chunk_size=chunk_size)

    def load_more_tracks(self, chat_id: int) -> None:
        self._tracks.load_chat_tracks(chat_id, reset=False)

    def set_socks5_proxy(self, server: str, port: int, username: str = "", password: str = "") -> None:
        self._adapter.send({
            "@type": "addProxy",
            "proxy": {
                "@type": "proxy",
                "server": server.strip(),
                "port": int(port),
                "last_used_date": 0,
                "type": {"@type": "proxyTypeSocks5", "username": username, "password": password},
            },
            "enable": True,
        })

    def set_http_proxy(self, server: str, port: int, username: str = "", password: str = "") -> None:
        self._adapter.send({
            "@type": "addProxy",
            "proxy": {
                "@type": "proxy",
                "server": server.strip(),
                "port": int(port),
                "last_used_date": 0,
                "type": {"@type": "proxyTypeHttp", "username": username, "password": password},
            },
            "enable": True,
        })

    def log_out(self) -> None:
        self._net_timer.stop()
        self._adapter.send({"@type": "logOut"})

    def stop(self) -> None:
        self._net_timer.stop()
        if self._worker:
            self._worker.stop()