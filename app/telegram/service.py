import base64
import logging
from pathlib import Path
from typing import Any
from PySide6.QtCore import QObject, QTimer, Signal, Slot

from app.config import AppConfig
from app.models.chat import OwnedChat
from app.models.track import Track
from app.models.user import TelegramUser
from app.settings.service import ProxySettings, SettingsService
from app.telegram.adapter import TDLibAdapter
from app.telegram.auth_handler import AuthHandler
from app.telegram.chat_handler import ChatHandler
from app.telegram.connection_manager import ConnectionManager
from app.telegram.enums import AuthState
from app.telegram.media_handler import MediaHandler
from app.telegram.track_handler import TrackHandler
from app.telegram.user_handler import UserHandler
from app.telegram.worker import TDLibWorker

logger = logging.getLogger("tmusic.telegram.service")


class TelegramService(QObject):
    """High-level Telegram service orchestrating authentication, user profile, chats, tracks, and media."""

    auth_state_changed = Signal(str)
    auth_error = Signal(str)
    connection_state_changed = Signal(str)
    connection_retry_interval_changed = Signal(int)

    user_loaded = Signal(TelegramUser)
    owned_chats_loaded = Signal(list)
    chat_selected = Signal(object)

    tracks_loaded = Signal(object, list, bool)
    tracks_appended = Signal(object, list, bool)
    tracks_prepended = Signal(object, list)
    tracks_deleted = Signal(object, list)
    cover_downloaded = Signal(str, str)
    track_reaction_updated = Signal(object, object, bool, int)

    file_download_progress = Signal(int, int, int)
    file_download_completed = Signal(int, str)
    network_traffic_received = Signal(int, int)

    search_results_received = Signal(object, list, bool)
    chat_search_results_received = Signal(list)

    def __init__(
        self,
        config: AppConfig,
        adapter: TDLibAdapter,
        settings_service: SettingsService | None = None,
        cache_manager: Any = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._adapter = adapter
        self._settings = settings_service
        self._cache = cache_manager
        self._worker: TDLibWorker | None = None
        self._current_opened_chat_id = 0

        self._connection = ConnectionManager(
            adapter=self._adapter,
            get_proxy_settings=lambda: self._settings.preferences.proxy if self._settings else None,
        )
        self._connection.retry_interval_changed.connect(self.connection_retry_interval_changed.emit)

        self._auth = AuthHandler(
            config=self._config,
            adapter=self._adapter,
            on_auth_state_changed=self._on_auth_state_changed,
            on_auth_ready=self._on_auth_ready,
            on_auth_closed=self._on_auth_closed,
        )

        self._user_handler = UserHandler(
            config=self._config,
            adapter=self._adapter,
            settings_service=self._settings,
            on_user_loaded=self.user_loaded.emit,
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
            on_search_results=self.chat_search_results_received.emit,
        )

        self._tracks = TrackHandler(
            adapter=self._adapter,
            request_cover_download=self._media.download_cover_file,
            register_file_path=self._media.register_completed_path,
            on_initial_chunk_loaded=self.tracks_loaded.emit,
            on_lazy_chunk_appended=self.tracks_appended.emit,
            on_delta_tracks_prepended=self.tracks_prepended.emit,
            on_tracks_deleted=self.tracks_deleted.emit,
            on_search_results=self.search_results_received.emit,
            on_track_reaction_updated=self.track_reaction_updated.emit,
        )

        self._net_timer = QTimer(self)
        self._net_timer.setInterval(1000)
        self._net_timer.timeout.connect(self._poll_network_statistics)

    @property
    def current_user(self) -> TelegramUser | None:
        return self._user_handler.current_user

    @property
    def current_auth_state(self) -> AuthState:
        return self._auth.current_state

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
        elif not self._media.has_active_downloads:
            self._net_timer.stop()

    def load_cached_state(self) -> None:
        self._chats.load_cached_chats()
        self._user_handler.load_cached_user()

    def get_downloaded_path(self, file_id: int) -> str | None:
        return self._media.get_downloaded_path(file_id)

    def register_downloaded_path(self, file_id: int, path: str) -> None:
        self._media.register_completed_path(file_id, path)

    def get_file_header_bytes(self, file_id: int, size: int = 131072) -> bytes | None:
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
            self.auth_error.emit("TDLib binary is missing or failed to load.")
            return

        self._worker = TDLibWorker(self._adapter)
        self._worker.update_received.connect(self._handle_update)
        self._worker.start()
        logger.info("TelegramService worker started")

    def _open_chat(self, chat_id: int) -> None:
        if self._current_opened_chat_id == chat_id:
            return
        if self._current_opened_chat_id != 0 and self._adapter.is_loaded:
            try:
                self._adapter.send({"@type": "closeChat", "chat_id": self._current_opened_chat_id})
            except Exception:
                pass
        self._current_opened_chat_id = chat_id
        if self._adapter.is_loaded:
            try:
                self._adapter.send({"@type": "openChat", "chat_id": chat_id})
            except Exception:
                pass

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

        if isinstance(extra, str) and extra.startswith("react_") and update_type == "error":
            parts = extra.split("_")
            if len(parts) >= 4:
                try:
                    err_chat_id, err_msg_id, attempted = int(parts[1]), int(parts[2]), bool(int(parts[3]))
                    self._tracks.revert_track_reaction(err_chat_id, err_msg_id, not attempted)
                except Exception:
                    pass
            return

        if extra == "periodic_net_stats" and update_type == "networkStatistics":
            total_rx = sum(e.get("received_bytes", 0) for e in update.get("entries", []))
            total_tx = sum(e.get("sent_bytes", 0) for e in update.get("entries", []))
            self.network_traffic_received.emit(total_rx, total_tx)
            return

        if isinstance(extra, str) and extra.startswith("load_tracks_"):
            parts = extra.split("_")
            chat_id = int(parts[2])
            is_initial = parts[3] == "initial"
            if update_type in ("foundChatMessages", "messages"):
                self._tracks.process_search_response(
                    chat_id, update.get("messages", []), update.get("next_from_message_id", 0), is_initial
                )
            elif update_type == "error" and is_initial:
                self.tracks_loaded.emit(chat_id, [], False)
            return

        if isinstance(extra, str) and extra.startswith("search_tracks_"):
            if update_type in ("foundChatMessages", "messages"):
                parts = extra.split("_")
                if len(parts) >= 3:
                    try:
                        cid = int(parts[2])
                        self._tracks.process_search_page(
                            cid, update.get("messages", []), update.get("next_from_message_id", 0), 100, extra
                        )
                    except ValueError:
                        pass
            return

        if isinstance(extra, str) and extra.startswith("search_chats_"):
            if update_type == "chats":
                self._chats.process_search_results(update.get("chat_ids", []), extra)
            return

        if isinstance(extra, str) and extra.startswith("search_chat_details_"):
            if update_type == "chat":
                parts = extra.split("_")
                if len(parts) >= 5:
                    search_id = "_".join(parts[3:-1])
                    try:
                        cid = int(parts[-1])
                        self._chats.process_chat_details_from_search(search_id, cid, update)
                    except ValueError:
                        pass
            return

        if extra in ("load_main_chats", "load_archive_chats"):
            self._chats.handle_pagination_response(extra, update_type)
            return

        if isinstance(extra, str) and extra.startswith("check_supergroup_") and update_type == "supergroup":
            self._chats.process_supergroup_update(update)
            return

        match update_type:
            case "updateAuthorizationState":
                self._auth.process_update(update.get("authorization_state", {}))

            case "updateConnectionState":
                state = update.get("state", {}).get("@type", "")
                self._connection.handle_connection_state(state)
                self.connection_state_changed.emit(state)

            case "updateNewMessage":
                self._tracks.process_new_message(update.get("message", {}))

            case "updateDeleteMessages":
                if update.get("is_permanent", True) and not update.get("from_cache", False):
                    self._tracks.process_delete_messages(update.get("chat_id", 0), update.get("message_ids", []))

            case "updateMessageInteractionInfo":
                self._tracks.process_interaction_info_update(
                    update.get("chat_id", 0), update.get("message_id", 0), update.get("interaction_info")
                )

            case "updateMessageReactions":
                self._tracks.process_reactions_update(
                    update.get("chat_id", 0), update.get("message_id", 0), update.get("reactions")
                )

            case "updateFile":
                file_obj = update.get("file", {})
                fid = file_obj.get("id", 0)
                local = file_obj.get("local", {})
                if local.get("is_downloading_completed") and local.get("path"):
                    if fid == self._user_handler.avatar_file_id:
                        self._user_handler.handle_avatar_file(Path(local.get("path")))
                    self._media.process_file_update(file_obj)

            case "user":
                self._user_handler.extract_user(update, is_self=True)

            case "updateUser":
                user_obj = update.get("user", {})
                if self._user_handler.my_user_id == 0 or user_obj.get("id", 0) == self._user_handler.my_user_id:
                    self._user_handler.extract_user(user_obj, is_self=True)

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

    def _on_auth_state_changed(self, state: AuthState) -> None:
        self.auth_state_changed.emit(state.value)

    def _on_auth_ready(self) -> None:
        self.set_online_status(True)
        self._chats.start_chat_sync()

    def _on_auth_closed(self) -> None:
        self._net_timer.stop()
        self._connection.stop()
        if self._worker:
            self._worker.stop()
            self._worker = None
        self._adapter.close()
        self.auth_state_changed.emit(AuthState.CLOSED.value)

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

    def toggle_track_like(self, track: Track) -> None:
        next_liked = not track.is_liked
        next_count = max(0, track.heart_count + (1 if next_liked else -1))
        self._open_chat(track.chat_id)
        self.track_reaction_updated.emit(track.chat_id, track.message_id, next_liked, next_count)
        self._tracks.toggle_track_like(track.chat_id, track.message_id, track.is_liked)

    def load_chat_tracks(self, chat_id: int, reset: bool = True, chunk_size: int = 40) -> None:
        if reset:
            self._open_chat(chat_id)
        self._tracks.load_chat_tracks(chat_id, reset=reset, chunk_size=chunk_size)

    def load_more_tracks(self, chat_id: int) -> None:
        self._tracks.load_chat_tracks(chat_id, reset=False)

    @Slot(str, str)
    def search_tracks(self, chat_id_str: str, query: str) -> None:
        try:
            cid = int(chat_id_str)
            self._tracks.search_tracks(cid, query)
        except ValueError:
            pass

    @Slot(str)
    def search_chats(self, query: str) -> None:
        self._chats.search_chats(query)

    def apply_proxy_settings(self, proxy: ProxySettings) -> None:
        self._connection.apply_proxy_settings(proxy)

    def log_out(self) -> None:
        self._net_timer.stop()
        self._connection.stop()
        self._adapter.send({"@type": "logOut"})

    def stop(self) -> None:
        self._net_timer.stop()
        self._connection.stop()
        if self._worker:
            self._worker.stop()
            self._worker = None