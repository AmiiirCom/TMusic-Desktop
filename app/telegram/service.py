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
from app.telegram.enums import AuthState
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
    """High-speed Telegram service with full network statistics and lazy track loading."""

    auth_state_changed = Signal(str)
    auth_error = Signal(str)
    connection_state_changed = Signal(str)

    user_loaded = Signal(TelegramUser)
    owned_chats_loaded = Signal(list)
    chat_selected = Signal(object)

    tracks_loaded = Signal(object, list, bool)
    tracks_appended = Signal(object, list, bool)
    cover_downloaded = Signal(str, str)

    file_download_progress = Signal(int, int, int)
    file_download_completed = Signal(int, str)

    # Precision Network Stats Signal: (total_received_bytes, total_sent_bytes)
    network_traffic_received = Signal(int, int)

    def __init__(
        self,
        config: AppConfig,
        adapter: TDLibAdapter,
        settings_service: SettingsService | None = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._adapter = adapter
        self._settings = settings_service
        self._worker: TDLibWorker | None = None
        self._auth_state = AuthState.UNKNOWN
        self._connection_state = "waiting_for_network"

        # Internal State
        self._my_user_id: int = 0
        self._current_user: TelegramUser | None = None
        self._raw_chats: dict[int, dict[str, Any]] = {}
        self._supergroups: dict[int, dict[str, Any]] = {}
        self._basic_groups: dict[int, dict[str, Any]] = {}
        self._owned_chats: dict[int, OwnedChat] = {}
        self._downloading_files: set[int] = set()
        self._file_id_to_path: dict[int, str] = {}
        self._cover_file_to_track_id: dict[int, str] = {}

        # Per-chat Track Pagination state
        self._track_pagination: dict[int, ChatTrackPaginationState] = {}

        # Loading trackers
        self._loading_main_chats = False
        self._loading_archive_chats = False

        # Live Network Statistics Poller Timer (Every 1 second)
        self._net_timer = QTimer(self)
        self._net_timer.setInterval(1000)
        self._net_timer.timeout.connect(self._poll_network_statistics)

    @property
    def current_user(self) -> TelegramUser | None:
        return self._current_user

    @property
    def current_auth_state(self) -> AuthState:
        return self._auth_state

    def set_settings_service(self, settings_service: SettingsService) -> None:
        self._settings = settings_service

    def load_cached_music_chats(self) -> None:
        if self._settings:
            cached = self._settings.get_cached_music_chats()
            if cached:
                for c in cached:
                    self._owned_chats[c.id] = c
                logger.info("Instantly loaded %d music channels from local cache ⚡", len(cached))
                self.owned_chats_loaded.emit(list(self._owned_chats.values()))

    def get_downloaded_path(self, file_id: int) -> str | None:
        path = self._file_id_to_path.get(file_id)
        if path and Path(path).exists():
            return path
        return None

    def start(self) -> None:
        if not self._adapter.is_loaded:
            logger.error("Cannot start TelegramService: TDLib is not loaded")
            self.auth_error.emit("TDLib binary is missing or failed to load.")
            return

        self._worker = TDLibWorker(self._adapter)
        self._worker.update_received.connect(self._handle_update)
        self._worker.start()
        self._net_timer.start()
        logger.info("TelegramService and Network Monitor started")

    def _poll_network_statistics(self) -> None:
        """Query TDLib for full accurate network usage."""
        if self._adapter.is_loaded:
            self._adapter.send({
                "@type": "getNetworkStatistics",
                "only_current": False,
                "@extra": "periodic_net_stats",
            })

    def _handle_update(self, update: dict[str, Any]) -> None:
        update_type = update.get("@type", "")
        extra = update.get("@extra", "")

        # 1. Handle Network Statistics
        if extra == "periodic_net_stats" and update_type == "networkStatistics":
            total_rx = 0
            total_tx = 0
            for entry in update.get("entries", []):
                total_rx += entry.get("received_bytes", 0)
                total_tx += entry.get("sent_bytes", 0)
            self.network_traffic_received.emit(total_rx, total_tx)
            return

        # 2. Chunked Track Search Responses
        if isinstance(extra, str) and extra.startswith("load_tracks_"):
            parts = extra.split("_")
            chat_id = int(parts[2])
            is_initial = parts[3] == "initial"

            if update_type in ("foundChatMessages", "messages"):
                messages = update.get("messages", [])
                next_from_id = update.get("next_from_message_id", 0)
                self._process_chat_audio_messages(chat_id, messages, next_from_id, is_initial)
            elif update_type == "error":
                logger.error("Failed to load tracks chunk for chat %d: %s", chat_id, update.get("message"))
                if is_initial:
                    self.tracks_loaded.emit(chat_id, [], False)
            return

        # 3. Chat Pagination Responses
        if extra == "load_main_chats":
            if update_type == "ok":
                self._load_next_main_chats()
            elif update_type == "error":
                logger.info("Main chats stream complete (%d chats). Loading archive...", len(self._raw_chats))
                self._loading_main_chats = False
                self._load_archive_chats()
            return

        if extra == "load_archive_chats":
            if update_type == "ok":
                self._load_next_archive_chats()
            elif update_type == "error":
                logger.info("Archive stream complete. Total chats scanned: %d", len(self._raw_chats))
                self._loading_archive_chats = False
            return

        # 4. Direct response from getSupergroup checks
        if isinstance(extra, str) and extra.startswith("check_supergroup_"):
            chat_id = int(extra.replace("check_supergroup_", ""))
            if update_type == "supergroup":
                sg_id = update.get("id", 0)
                self._supergroups[sg_id] = update
                self._evaluate_chat_ownership(chat_id)
            return

        # 5. General Update Streams
        match update_type:
            case "updateAuthorizationState":
                self._process_auth_state(update.get("authorization_state", {}))

            case "updateConnectionState":
                state = update.get("state", {}).get("@type", "")
                self._connection_state = state
                self.connection_state_changed.emit(state)

            case "updateFile":
                file_obj = update.get("file", {})
                self._process_file_update(file_obj)

            case "user":
                self._extract_user(update, is_self=True)

            case "updateUser":
                user_obj = update.get("user", {})
                if self._my_user_id == 0 or user_obj.get("id") == self._my_user_id:
                    self._extract_user(user_obj, is_self=True)

            case "chats":
                chat_ids = update.get("chat_ids", [])
                for cid in chat_ids:
                    self._adapter.send({"@type": "getChat", "chat_id": cid})

            case "updateNewChat":
                chat = update.get("chat", {})
                chat_id = chat.get("id", 0)
                self._raw_chats[chat_id] = chat
                self._evaluate_chat_ownership(chat_id)

            case "updateSupergroup":
                sg = update.get("supergroup", {})
                sg_id = sg.get("id", 0)
                self._supergroups[sg_id] = sg
                self._recheck_supergroup_chats(sg_id)

            case "supergroup":
                sg_id = update.get("id", 0)
                self._supergroups[sg_id] = update
                self._recheck_supergroup_chats(sg_id)

            case "updateBasicGroup":
                bg = update.get("basic_group", {})
                bg_id = bg.get("id", 0)
                self._basic_groups[bg_id] = bg
                self._recheck_basicgroup_chats(bg_id)

            case "updateChatTitle":
                chat_id = update.get("chat_id", 0)
                new_title = update.get("title", "")
                if chat_id in self._raw_chats:
                    self._raw_chats[chat_id]["title"] = new_title

                if chat_id in self._owned_chats:
                    if is_music_title(new_title):
                        old = self._owned_chats[chat_id]
                        self._owned_chats[chat_id] = OwnedChat(
                            id=old.id,
                            title=new_title,
                            is_channel=old.is_channel,
                            supergroup_id=old.supergroup_id,
                            unread_count=old.unread_count,
                        )
                    else:
                        del self._owned_chats[chat_id]
                    self._sync_and_emit_owned_chats()
                else:
                    self._evaluate_chat_ownership(chat_id)

            case "error":
                code = update.get("code")
                msg = update.get("message", "")
                if code != 404:
                    logger.warning("TDLib Error: %s (code: %s)", msg, code)

    def _process_auth_state(self, auth_state_obj: dict[str, Any]) -> None:
        state_type = auth_state_obj.get("@type", "")
        logger.info("TDLib Auth State: %s", state_type)

        match state_type:
            case "authorizationStateWaitTdlibParameters":
                self._auth_state = AuthState.WAIT_TDLIB_PARAMETERS
                self._send_tdlib_parameters()

            case "authorizationStateWaitPhoneNumber":
                self._auth_state = AuthState.WAIT_PHONE_NUMBER

            case "authorizationStateWaitCode":
                self._auth_state = AuthState.WAIT_CODE

            case "authorizationStateWaitPassword":
                self._auth_state = AuthState.WAIT_PASSWORD

            case "authorizationStateReady":
                self._auth_state = AuthState.READY
                logger.info("Authorization READY! Launching continuous chat sync...")
                self._adapter.send({"@type": "getMe"})
                self._adapter.send({
                    "@type": "getCreatedPublicChats",
                    "type": {"@type": "publicChatTypeHasUsername"},
                })
                self._start_chat_loading()

            case "authorizationStateLoggingOut":
                self._auth_state = AuthState.LOGGING_OUT

            case "authorizationStateClosed":
                self._auth_state = AuthState.CLOSED

            case _:
                self._auth_state = AuthState.UNKNOWN

        self.auth_state_changed.emit(self._auth_state.value)

    def _send_tdlib_parameters(self) -> None:
        self._config.ensure_directories()
        params = {
            "@type": "setTdlibParameters",
            "use_test_dc": False,
            "database_directory": str(self._config.tdlib_dir),
            "files_directory": str(self._config.cache_dir),
            "use_file_database": True,
            "use_chat_info_database": True,
            "use_message_database": True,
            "use_secret_chats": False,
            "api_id": self._config.api_id,
            "api_hash": self._config.api_hash,
            "system_language_code": "fa",
            "device_model": "Desktop",
            "system_version": "Windows",
            "application_version": self._config.app_version,
            "enable_storage_optimizer": True,
        }
        self._adapter.send(params)

    # --- Fast Stream Chat Loading ---

    def _start_chat_loading(self) -> None:
        self._loading_main_chats = True
        self._load_next_main_chats()

    def _load_next_main_chats(self) -> None:
        self._adapter.send({
            "@type": "loadChats",
            "chat_list": {"@type": "chatListMain"},
            "limit": 100,
            "@extra": "load_main_chats",
        })

    def _load_archive_chats(self) -> None:
        self._loading_archive_chats = True
        self._load_next_archive_chats()

    def _load_next_archive_chats(self) -> None:
        self._adapter.send({
            "@type": "loadChats",
            "chat_list": {"@type": "chatListArchive"},
            "limit": 100,
            "@extra": "load_archive_chats",
        })

    def _evaluate_chat_ownership(self, chat_id: int) -> None:
        chat = self._raw_chats.get(chat_id)
        if not chat:
            return

        title = chat.get("title", "")
        if not is_music_title(title):
            return

        chat_type = chat.get("type", {})
        type_str = chat_type.get("@type", "")

        if type_str == "chatTypeSupergroup":
            sg_id = chat_type.get("supergroup_id", 0)
            if sg_id in self._supergroups:
                sg = self._supergroups[sg_id]
                status = sg.get("status", {}).get("@type", "")
                if status == "chatMemberStatusCreator" or sg.get("is_creator", False):
                    self._add_owned_chat(
                        chat_id=chat_id,
                        title=title,
                        is_channel=sg.get("is_channel", True),
                        supergroup_id=sg_id,
                        unread_count=chat.get("unread_count", 0),
                    )
            else:
                self._adapter.send({
                    "@type": "getSupergroup",
                    "supergroup_id": sg_id,
                    "@extra": f"check_supergroup_{chat_id}",
                })

        elif type_str == "chatTypeBasicGroup":
            bg_id = chat_type.get("basic_group_id", 0)
            if bg_id in self._basic_groups:
                bg = self._basic_groups[bg_id]
                status = bg.get("status", {}).get("@type", "")
                if status == "chatMemberStatusCreator" or bg.get("is_creator", False):
                    self._add_owned_chat(
                        chat_id=chat_id,
                        title=title,
                        is_channel=False,
                        supergroup_id=0,
                        unread_count=chat.get("unread_count", 0),
                    )

    def _recheck_supergroup_chats(self, sg_id: int) -> None:
        for chat_id, chat in self._raw_chats.items():
            chat_type = chat.get("type", {})
            if (
                chat_type.get("@type") == "chatTypeSupergroup"
                and chat_type.get("supergroup_id") == sg_id
            ):
                self._evaluate_chat_ownership(chat_id)

    def _recheck_basicgroup_chats(self, bg_id: int) -> None:
        for chat_id, chat in self._raw_chats.items():
            chat_type = chat.get("type", {})
            if (
                chat_type.get("@type") == "chatTypeBasicGroup"
                and chat_type.get("basic_group_id") == bg_id
            ):
                self._evaluate_chat_ownership(chat_id)

    def _add_owned_chat(
        self, chat_id: int, title: str, is_channel: bool, supergroup_id: int, unread_count: int
    ) -> None:
        if chat_id in self._owned_chats:
            return

        if not is_music_title(title):
            return

        owned_chat = OwnedChat(
            id=chat_id,
            title=title,
            is_channel=is_channel,
            supergroup_id=supergroup_id,
            unread_count=unread_count,
        )
        self._owned_chats[chat_id] = owned_chat
        logger.info("Found owned music chat: %s (ID: %d)", title, chat_id)
        self._sync_and_emit_owned_chats()

    def _sync_and_emit_owned_chats(self) -> None:
        chat_list = list(self._owned_chats.values())
        if self._settings:
            self._settings.set_cached_music_chats(chat_list)
        self.owned_chats_loaded.emit(chat_list)

    # --- Media Download & Playback Support ---

    def download_file(self, file_id: int) -> None:
        if file_id in self._file_id_to_path and Path(self._file_id_to_path[file_id]).exists():
            self.file_download_completed.emit(file_id, self._file_id_to_path[file_id])
            return

        if file_id in self._downloading_files:
            return

        self._downloading_files.add(file_id)
        logger.info("Requesting TDLib download for file ID: %d", file_id)
        self._adapter.send({
            "@type": "downloadFile",
            "file_id": file_id,
            "priority": 32,
            "offset": 0,
            "limit": 0,
            "synchronous": False,
        })

    def download_cover(self, track_id: str, file_id: int) -> None:
        if not file_id:
            return

        self._cover_file_to_track_id[file_id] = track_id

        if file_id in self._file_id_to_path and Path(self._file_id_to_path[file_id]).exists():
            self.cover_downloaded.emit(track_id, self._file_id_to_path[file_id])
            return

        self._adapter.send({
            "@type": "downloadFile",
            "file_id": file_id,
            "priority": 4,
            "offset": 0,
            "limit": 0,
            "synchronous": False,
        })

    def _process_file_update(self, file_obj: dict[str, Any]) -> None:
        file_id = file_obj.get("id", 0)
        local = file_obj.get("local", {})
        is_completed = local.get("is_downloading_completed", False)
        path = local.get("path", "")
        downloaded = local.get("downloaded_size", 0)
        total = file_obj.get("size", 0) or file_obj.get("expected_size", 0)

        if is_completed and path:
            self._file_id_to_path[file_id] = path

            track_id = self._cover_file_to_track_id.get(file_id)
            if track_id:
                self.cover_downloaded.emit(track_id, path)

            if file_id in self._downloading_files:
                self._downloading_files.discard(file_id)
                logger.info("File ID %d download completed! Path: %s", file_id, path)
                self.file_download_completed.emit(file_id, path)

        elif local.get("is_downloading_active", False):
            self.file_download_progress.emit(file_id, downloaded, total)

    # --- Chunked Lazy Music Loading with HD Cover Extraction ---

    def load_chat_tracks(self, chat_id: int, reset: bool = True, chunk_size: int = 40) -> None:
        if reset or chat_id not in self._track_pagination:
            state = ChatTrackPaginationState(chat_id=chat_id)
            self._track_pagination[chat_id] = state
        else:
            state = self._track_pagination[chat_id]

        if state.is_loading or not state.has_more:
            return

        state.is_loading = True
        is_initial_str = "initial" if reset else "lazy"
        from_msg_id = state.next_from_message_id if not reset else 0

        logger.info(
            "Loading tracks chunk for chat %d (from_id=%d, limit=%d, type=%s)...",
            chat_id, from_msg_id, chunk_size, is_initial_str
        )

        self._adapter.send({
            "@type": "searchChatMessages",
            "chat_id": chat_id,
            "query": "",
            "from_message_id": from_msg_id,
            "offset": 0,
            "limit": chunk_size,
            "filter": {"@type": "searchMessagesFilterAudio"},
            "@extra": f"load_tracks_{chat_id}_{is_initial_str}",
        })

    def load_more_tracks(self, chat_id: int) -> None:
        self.load_chat_tracks(chat_id, reset=False)

    def _process_chat_audio_messages(
        self, chat_id: int, messages: list[dict[str, Any]], next_from_id: int, is_initial: bool
    ) -> None:
        state = self._track_pagination.get(chat_id)
        if not state:
            state = ChatTrackPaginationState(chat_id=chat_id)
            self._track_pagination[chat_id] = state

        state.is_loading = False
        state.next_from_message_id = next_from_id
        state.has_more = (next_from_id != 0) and (len(messages) > 0)

        chunk_tracks: list[Track] = []
        for msg in messages:
            content = msg.get("content", {})
            content_type = content.get("@type", "")
            msg_date = msg.get("date", 0)
            msg_id = msg.get("id", 0)
            track_id = f"{chat_id}_{msg_id}"

            if content_type == "messageAudio":
                audio = content.get("audio", {})
                file_obj = audio.get("audio", {})
                local_file = file_obj.get("local", {})
                file_id = file_obj.get("id", 0)
                path = local_file.get("path", "")

                minithumb = audio.get("album_cover_minithumbnail")
                minithumb_data: bytes | None = None
                if minithumb and "data" in minithumb:
                    try:
                        minithumb_data = base64.b64decode(minithumb["data"])
                    except Exception:
                        minithumb_data = None

                hd_thumb = audio.get("album_cover_thumbnail") or audio.get("thumbnail")
                cover_file_id = 0
                cover_path = None
                if hd_thumb:
                    c_file = hd_thumb.get("file", {})
                    cover_file_id = c_file.get("id", 0)
                    c_local = c_file.get("local", {})
                    if c_local.get("is_downloading_completed") and c_local.get("path"):
                        cover_path = c_local.get("path")
                    elif cover_file_id > 0:
                        self.download_cover(track_id, cover_file_id)

                if local_file.get("is_downloading_completed") and path:
                    self._file_id_to_path[file_id] = path

                track = Track(
                    id=track_id,
                    chat_id=chat_id,
                    message_id=msg_id,
                    file_id=file_id,
                    title=audio.get("title", ""),
                    artist=audio.get("performer", ""),
                    duration_seconds=audio.get("duration", 0),
                    size_bytes=file_obj.get("size", 0) or file_obj.get("expected_size", 0),
                    file_name=audio.get("file_name", ""),
                    mime_type=audio.get("mime_type", "audio/mpeg"),
                    local_path=path if (local_file.get("is_downloading_completed") and Path(path).exists()) else None,
                    is_downloaded=local_file.get("is_downloading_completed", False),
                    date_timestamp=msg_date,
                    minithumbnail_data=minithumb_data,
                    cover_file_id=cover_file_id,
                    cover_path=cover_path,
                )
                chunk_tracks.append(track)

            elif content_type == "messageDocument":
                doc = content.get("document", {})
                file_name = doc.get("file_name", "")
                mime_type = doc.get("mime_type", "")

                audio_exts = (".mp3", ".flac", ".m4a", ".wav", ".aac", ".ogg", ".opus")
                if mime_type.startswith("audio/") or file_name.lower().endswith(audio_exts):
                    file_obj = doc.get("document", {})
                    local_file = file_obj.get("local", {})
                    file_id = file_obj.get("id", 0)
                    path = local_file.get("path", "")

                    minithumb = doc.get("minithumbnail")
                    minithumb_data = None
                    if minithumb and "data" in minithumb:
                        try:
                            minithumb_data = base64.b64decode(minithumb["data"])
                        except Exception:
                            minithumb_data = None

                    hd_thumb = doc.get("thumbnail")
                    cover_file_id = 0
                    cover_path = None
                    if hd_thumb:
                        c_file = hd_thumb.get("file", {})
                        cover_file_id = c_file.get("id", 0)
                        c_local = c_file.get("local", {})
                        if c_local.get("is_downloading_completed") and c_local.get("path"):
                            cover_path = c_local.get("path")
                        elif cover_file_id > 0:
                            self.download_cover(track_id, cover_file_id)

                    if local_file.get("is_downloading_completed") and path:
                        self._file_id_to_path[file_id] = path

                    track = Track(
                        id=track_id,
                        chat_id=chat_id,
                        message_id=msg_id,
                        file_id=file_id,
                        title=file_name,
                        artist="Audio File",
                        duration_seconds=0,
                        size_bytes=file_obj.get("size", 0) or file_obj.get("expected_size", 0),
                        file_name=file_name,
                        mime_type=mime_type or "audio/mpeg",
                        local_path=path if (local_file.get("is_downloading_completed") and Path(path).exists()) else None,
                        is_downloaded=local_file.get("is_downloading_completed", False),
                        date_timestamp=msg_date,
                        minithumbnail_data=minithumb_data,
                        cover_file_id=cover_file_id,
                        cover_path=cover_path,
                    )
                    chunk_tracks.append(track)

        if is_initial:
            state.tracks = list(chunk_tracks)
            logger.info("Initial chunk for chat %d: %d tracks (has_more: %s)", chat_id, len(chunk_tracks), state.has_more)
            self.tracks_loaded.emit(chat_id, state.tracks, state.has_more)
        else:
            state.tracks.extend(chunk_tracks)
            logger.info("Lazy chunk for chat %d: %d new tracks (total: %d, has_more: %s)", chat_id, len(chunk_tracks), len(state.tracks), state.has_more)
            self.tracks_appended.emit(chat_id, chunk_tracks, state.has_more)

    def _extract_user(self, user_obj: dict[str, Any], is_self: bool = False) -> None:
        user_id = user_obj.get("id", 0)
        if not user_id:
            return

        usernames = user_obj.get("usernames", {})
        active_usernames = usernames.get("active_usernames", [])
        username = active_usernames[0] if active_usernames else user_obj.get("username", "")

        user = TelegramUser(
            id=user_id,
            first_name=user_obj.get("first_name", ""),
            last_name=user_obj.get("last_name", ""),
            username=username,
            phone_number=user_obj.get("phone_number", ""),
        )

        if is_self or self._my_user_id == user_id:
            self._my_user_id = user_id
            self._current_user = user
            logger.info("Current user profile: %s (ID: %d)", user.full_name, user.id)
            self.user_loaded.emit(user)

    # --- Secure Auth Action Guards ---

    def send_phone_number(self, phone_number: str) -> None:
        if self._auth_state != AuthState.WAIT_PHONE_NUMBER:
            logger.warning("Ignoring phone submission: Auth state is %s", self._auth_state)
            return

        self._adapter.send({
            "@type": "setAuthenticationPhoneNumber",
            "phone_number": phone_number.strip(),
            "settings": {"@type": "phoneNumberAuthenticationSettings"},
        })

    def send_code(self, code: str) -> None:
        if self._auth_state != AuthState.WAIT_CODE:
            logger.warning("Ignoring code submission: Auth state is %s", self._auth_state)
            return

        self._adapter.send({"@type": "checkAuthenticationCode", "code": code.strip()})

    def send_password(self, password: str) -> None:
        if self._auth_state != AuthState.WAIT_PASSWORD:
            logger.warning("Ignoring password submission: Auth state is %s", self._auth_state)
            return

        self._adapter.send({"@type": "checkAuthenticationPassword", "password": password})

    def set_socks5_proxy(
        self, server: str, port: int, username: str = "", password: str = ""
    ) -> None:
        self._adapter.send({
            "@type": "addProxy",
            "proxy": {
                "@type": "proxy",
                "server": server.strip(),
                "port": int(port),
                "last_used_date": 0,
                "type": {
                    "@type": "proxyTypeSocks5",
                    "username": username,
                    "password": password,
                },
            },
            "enable": True,
        })

    def set_http_proxy(
        self, server: str, port: int, username: str = "", password: str = ""
    ) -> None:
        self._adapter.send({
            "@type": "addProxy",
            "proxy": {
                "@type": "proxy",
                "server": server.strip(),
                "port": int(port),
                "last_used_date": 0,
                "type": {
                    "@type": "proxyTypeHttp",
                    "username": username,
                    "password": password,
                    "http_only": False,
                },
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