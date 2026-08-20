import base64
import logging
from pathlib import Path
from typing import Any
from PySide6.QtCore import QObject, QTimer, Signal, Slot

from app.config import AppConfig
from app.models.chat import FAVORITES_CHAT_ID, OwnedChat
from app.models.track import Track
from app.models.user import TelegramUser
from app.settings.service import ProxySettings, SettingsService
from app.telegram.adapter import TDLibAdapter
from app.telegram.auth_handler import AuthHandler
from app.telegram.chat_handler import ChatHandler
from app.telegram.connection_manager import ConnectionManager
from app.telegram.enums import AuthState
from app.telegram.media_handler import MediaHandler
from app.telegram.reactions import extract_heart_reaction
from app.telegram.track_handler import TrackHandler
from app.telegram.track_parser import parse_message_to_track
from app.telegram.user_handler import UserHandler
from app.telegram.worker import TDLibWorker

logger = logging.getLogger("tmusic.telegram.service")


class TelegramService(QObject):
    """High-level Telegram service orchestrating authentication, profile, chats, tracks, and media."""

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
            on_cover_completed=self._on_cover_completed,
        )

        self._chats = ChatHandler(
            adapter=self._adapter,
            settings_service=self._settings,
            on_owned_chats_updated=self._on_owned_chats_loaded,
            on_search_results=self.chat_search_results_received.emit,
        )

        self._tracks = TrackHandler(
            adapter=self._adapter,
            request_cover_download=self._media.download_cover_file,
            register_file_path=self._media.register_completed_path,
            on_initial_chunk_loaded=self._on_initial_tracks_loaded,
            on_lazy_chunk_appended=self._on_lazy_tracks_appended,
            on_delta_tracks_prepended=self._on_delta_tracks_prepended,
            on_tracks_deleted=self.tracks_deleted.emit,
            on_search_results=self._on_search_results_received,
            on_track_reaction_updated=self._on_track_reaction_updated,
        )

        # Continuous background network traffic monitor
        self._net_timer = QTimer(self)
        self._net_timer.setInterval(1000)
        self._net_timer.timeout.connect(self._poll_network_statistics)

        # Universal smooth progressive cover loading queue (applied across all playlists)
        self._cover_queue: list[tuple[str, int]] = []
        self._cover_timer = QTimer(self)
        self._cover_timer.setInterval(60)  # Smooth 60ms cascade interval
        self._cover_timer.timeout.connect(self._process_next_cover)

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
        if is_active and not self._net_timer.isActive():
            self._net_timer.start()

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

        self._net_timer.start()
        self._poll_network_statistics()

        logger.info("TelegramService worker and Network Monitor started.")

    def _open_chat(self, chat_id: int) -> None:
        self._clear_cover_queue()

        if chat_id == FAVORITES_CHAT_ID:
            return

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

    def _sync_liked_tracks_from_list(self, tracks: list[Track]) -> None:
        if not self._settings:
            return
        for t in tracks:
            if t.is_liked:
                self._settings.save_liked_track(t)

    def _on_initial_tracks_loaded(self, chat_id: int, tracks: list[Track], has_more: bool) -> None:
        self._sync_liked_tracks_from_list(tracks)
        self.tracks_loaded.emit(chat_id, tracks, has_more)
        # Start smooth 1-by-1 cover cascade for initial batch
        self._start_staggered_covers(tracks, clear_existing=True)

    def _on_lazy_tracks_appended(self, chat_id: int, tracks: list[Track], has_more: bool) -> None:
        self._sync_liked_tracks_from_list(tracks)
        self.tracks_appended.emit(chat_id, tracks, has_more)
        # Append scroll pagination chunk to the ongoing smooth cover cascade
        self._start_staggered_covers(tracks, clear_existing=False)

    def _on_delta_tracks_prepended(self, chat_id: int, tracks: list[Track]) -> None:
        self._sync_liked_tracks_from_list(tracks)
        self.tracks_prepended.emit(chat_id, tracks)
        self._start_staggered_covers(tracks, clear_existing=False)

    def _on_search_results_received(self, chat_id: int, tracks: list[Track], has_more: bool) -> None:
        self.search_results_received.emit(chat_id, tracks, has_more)
        self._start_staggered_covers(tracks, clear_existing=True)

    def _on_cover_completed(self, track_id: str, cover_path: str) -> None:
        if self._settings:
            self._settings.update_liked_track_cover(track_id, cover_path)
        self.cover_downloaded.emit(track_id, cover_path)

    def _on_owned_chats_loaded(self, chats: list[OwnedChat]) -> None:
        self.owned_chats_loaded.emit(chats)
        self.sync_favorites_from_telegram()

    def _start_staggered_covers(self, tracks: list[Track], clear_existing: bool = True) -> None:
        """
        Universal staggered cover art loader: enqueues tracks and smoothly
        cascades HD cover downloads 1-by-1 across all chats and pagination chunks.
        """
        if clear_existing:
            self._cover_queue.clear()

        new_entries = [
            (t.id, t.cover_file_id)
            for t in tracks
            if t.cover_file_id > 0 and not (t.cover_path and Path(t.cover_path).exists())
        ]
        self._cover_queue.extend(new_entries)

        if self._cover_queue and not self._cover_timer.isActive():
            self._cover_timer.start()

    def _process_next_cover(self) -> None:
        """Pop and fetch one cover from queue at each timer interval."""
        if not self._cover_queue:
            self._cover_timer.stop()
            return

        track_id, cover_file_id = self._cover_queue.pop(0)
        self._media.download_cover_file(track_id, cover_file_id)

    def _clear_cover_queue(self) -> None:
        self._cover_timer.stop()
        self._cover_queue.clear()

    @staticmethod
    def _clone_track_lightweight(t: Track) -> Track:
        """Create a lightweight track copy for smooth initial rendering."""
        return Track(
            id=t.id,
            chat_id=t.chat_id,
            message_id=t.message_id,
            file_id=t.file_id,
            title=t.title,
            artist=t.artist,
            duration_seconds=t.duration_seconds,
            size_bytes=t.size_bytes,
            file_name=t.file_name,
            mime_type=t.mime_type,
            local_path=t.local_path,
            is_downloaded=t.is_downloaded,
            date_timestamp=t.date_timestamp,
            minithumbnail_data=t.minithumbnail_data,
            cover_file_id=t.cover_file_id,
            cover_path=None,
            is_liked=t.is_liked,
            heart_count=t.heart_count,
        )

    def sync_favorites_from_telegram(self) -> None:
        """Fetch and deeply sync liked audio tracks across owned music chats with full reaction verification."""
        if not self._adapter.is_loaded:
            return

        owned_chats = self._chats.get_all_owned_chats()
        if not owned_chats:
            self._adapter.send({
                "@type": "searchMessages",
                "chat_list": {"@type": "chatListMain"},
                "query": "",
                "offset": "",
                "limit": 100,
                "filter": {"@type": "searchMessagesFilterAudio"},
                "@extra": "sync_favorites_global",
            })
            return

        for chat in owned_chats:
            if not chat.is_favorites:
                self._fetch_favorites_page(chat.id, from_message_id=0)

    def _fetch_favorites_page(self, chat_id: int, from_message_id: int) -> None:
        """Request audio messages page and open chat context to force reaction synchronization."""
        if not self._adapter.is_loaded:
            return

        self._adapter.send({"@type": "openChat", "chat_id": chat_id})

        self._adapter.send({
            "@type": "searchChatMessages",
            "chat_id": chat_id,
            "query": "",
            "from_message_id": from_message_id,
            "offset": 0,
            "limit": 100,
            "filter": {"@type": "searchMessagesFilterAudio"},
            "@extra": f"sync_favorites_chat_{chat_id}_{from_message_id}",
        })

    def _on_track_reaction_updated(
        self, chat_id: int, message_id: int, is_liked: bool, heart_count: int
    ) -> None:
        track_id = f"{chat_id}_{message_id}"
        if is_liked:
            track = self._tracks.get_track(chat_id, message_id)
            if track:
                updated_track = Track(
                    id=track.id,
                    chat_id=track.chat_id,
                    message_id=track.message_id,
                    file_id=track.file_id,
                    title=track.title,
                    artist=track.artist,
                    duration_seconds=track.duration_seconds,
                    size_bytes=track.size_bytes,
                    file_name=track.file_name,
                    mime_type=track.mime_type,
                    local_path=track.local_path,
                    is_downloaded=track.is_downloaded,
                    date_timestamp=track.date_timestamp,
                    minithumbnail_data=track.minithumbnail_data,
                    cover_file_id=track.cover_file_id,
                    cover_path=track.cover_path,
                    is_liked=True,
                    heart_count=heart_count,
                )
                if self._settings:
                    self._settings.save_liked_track(updated_track)
                self.tracks_prepended.emit(FAVORITES_CHAT_ID, [updated_track])

                # Fetch HD cover for newly liked track
                if updated_track.cover_file_id > 0 and not updated_track.cover_path:
                    self._media.download_cover_file(updated_track.id, updated_track.cover_file_id)
            else:
                if self._adapter.is_loaded:
                    self._adapter.send({
                        "@type": "getMessage",
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "@extra": f"fetch_liked_msg_{chat_id}_{message_id}",
                    })
        else:
            # Unliked on Telegram: remove from storage and emit deletion signal
            if self._settings:
                self._settings.remove_liked_track(track_id)
            self.tracks_deleted.emit(FAVORITES_CHAT_ID, [track_id])

        self.track_reaction_updated.emit(chat_id, message_id, is_liked, heart_count)

    def _handle_update(self, update: dict[str, Any]) -> None:
        update_type = update.get("@type", "")
        extra = update.get("@extra", "")

        # Handle deep favorites history scan with live reaction delivery
        if isinstance(extra, str) and (extra.startswith("sync_favorites_chat_") or extra == "sync_favorites_global"):
            if update_type in ("foundChatMessages", "foundMessages", "messages"):
                messages = update.get("messages", [])
                next_from_id = update.get("next_from_message_id", 0)
                cid = 0
                if extra.startswith("sync_favorites_chat_"):
                    parts = extra.split("_")
                    if len(parts) >= 4:
                        try:
                            cid = int(parts[3])
                        except ValueError:
                            cid = 0

                msg_ids = [m["id"] for m in messages if isinstance(m, dict) and "id" in m]
                if msg_ids and cid != 0 and self._adapter.is_loaded:
                    self._adapter.send({
                        "@type": "viewMessages",
                        "chat_id": cid,
                        "message_ids": msg_ids,
                        "force_read": False,
                    })

                has_new_additions = False
                for msg in messages:
                    msg_cid = msg.get("chat_id", cid)
                    track = parse_message_to_track(
                        msg_cid, msg, request_cover_callback=None, register_path_callback=self._media.register_completed_path
                    )
                    if track:
                        if track.is_liked:
                            if self._settings:
                                is_new = self._settings.save_liked_track(track)
                                if is_new:
                                    has_new_additions = True
                        else:
                            if self._settings and any(lt.id == track.id for lt in self._settings.get_liked_tracks()):
                                self._settings.remove_liked_track(track.id)
                                self.tracks_deleted.emit(FAVORITES_CHAT_ID, [track.id])

                if has_new_additions and self._settings:
                    liked_tracks = self._settings.get_liked_tracks()
                    light_tracks = [self._clone_track_lightweight(t) for t in liked_tracks]
                    self.tracks_loaded.emit(FAVORITES_CHAT_ID, light_tracks, False)
                    self._start_staggered_covers(liked_tracks, clear_existing=True)

                if next_from_id != 0 and cid != 0:
                    self._fetch_favorites_page(cid, from_message_id=next_from_id)
            return

        # Handle individual message fetch for remote likes
        if isinstance(extra, str) and extra.startswith("fetch_liked_msg_"):
            if update_type == "message":
                chat_id = update.get("chat_id", 0)
                track = parse_message_to_track(
                    chat_id, update, self._media.download_cover_file, self._media.register_completed_path
                )
                if track:
                    is_liked, count = extract_heart_reaction(update)
                    if is_liked:
                        if self._settings:
                            self._settings.save_liked_track(track)
                        self.track_reaction_updated.emit(track.chat_id, track.message_id, True, count)
                        self.tracks_prepended.emit(FAVORITES_CHAT_ID, [track])
                        if track.cover_file_id > 0 and not track.cover_path:
                            self._media.download_cover_file(track.id, track.cover_file_id)
            return

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
                messages = update.get("messages", [])
                msg_ids = [m["id"] for m in messages if isinstance(m, dict) and "id" in m]
                if msg_ids and self._adapter.is_loaded:
                    self._adapter.send({
                        "@type": "viewMessages",
                        "chat_id": chat_id,
                        "message_ids": msg_ids,
                        "force_read": False,
                    })

                self._tracks.process_search_response(
                    chat_id, messages, update.get("next_from_message_id", 0), is_initial
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
                msg = update.get("message", {})
                self._tracks.process_new_message(msg)

            case "updateDeleteMessages":
                if update.get("is_permanent", True) and not update.get("from_cache", False):
                    self._tracks.process_delete_messages(update.get("chat_id", 0), update.get("message_ids", []))

            case "updateMessageInteractionInfo":
                cid = update.get("chat_id", 0)
                mid = update.get("message_id", 0)
                info = update.get("interaction_info")
                self._tracks.process_interaction_info_update(cid, mid, info)
                is_liked, count = extract_heart_reaction(info)
                self._on_track_reaction_updated(cid, mid, is_liked, count)

            case "updateMessageReactions":
                cid = update.get("chat_id", 0)
                mid = update.get("message_id", 0)
                reactions = update.get("reactions")
                self._tracks.process_reactions_update(cid, mid, reactions)
                is_liked, count = extract_heart_reaction({"reactions": reactions})
                self._on_track_reaction_updated(cid, mid, is_liked, count)

            case "updateFile":
                file_obj = update.get("file", {})
                fid = file_obj.get("id", 0)
                local = file_obj.get("local", {})
                if local.get("is_downloading_completed") and local.get("path"):
                    if fid == self._user_handler.avatar_file_id:
                        self._user_handler.handle_avatar_file(Path(local.get("path")))
                        return
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
        self.sync_favorites_from_telegram()

    def _on_auth_closed(self) -> None:
        self._net_timer.stop()
        self._clear_cover_queue()
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
        self._media.download_audio_file(file_id)

    def prefetch_audio_file(self, file_id: int) -> None:
        self._media.prefetch_audio_file(file_id)

    def prefetch_cover_file(self, track_id: str, file_id: int) -> None:
        self._media.download_cover_file(track_id, file_id)

    def toggle_track_like(self, track: Track) -> None:
        next_liked = not track.is_liked
        next_count = max(0, track.heart_count + (1 if next_liked else -1))

        if self._settings:
            if next_liked:
                updated_track = Track(
                    id=track.id,
                    chat_id=track.chat_id,
                    message_id=track.message_id,
                    file_id=track.file_id,
                    title=track.title,
                    artist=track.artist,
                    duration_seconds=track.duration_seconds,
                    size_bytes=track.size_bytes,
                    file_name=track.file_name,
                    mime_type=track.mime_type,
                    local_path=track.local_path,
                    is_downloaded=track.is_downloaded,
                    date_timestamp=track.date_timestamp,
                    minithumbnail_data=track.minithumbnail_data,
                    cover_file_id=track.cover_file_id,
                    cover_path=track.cover_path,
                    is_liked=True,
                    heart_count=next_count,
                )
                self._settings.save_liked_track(updated_track)
                self.tracks_prepended.emit(FAVORITES_CHAT_ID, [updated_track])

                if updated_track.cover_file_id > 0 and not updated_track.cover_path:
                    self._media.download_cover_file(updated_track.id, updated_track.cover_file_id)
            else:
                self._settings.remove_liked_track(track.id)
                self.tracks_deleted.emit(FAVORITES_CHAT_ID, [track.id])

        if track.chat_id != FAVORITES_CHAT_ID:
            self._open_chat(track.chat_id)
        self.track_reaction_updated.emit(track.chat_id, track.message_id, next_liked, next_count)
        self._tracks.toggle_track_like(track.chat_id, track.message_id, track.is_liked)

    def load_chat_tracks(self, chat_id: int, reset: bool = True, chunk_size: int = 40) -> None:
        if chat_id == FAVORITES_CHAT_ID:
            # Phase 1: Fast initial load with minithumbnails (lightweight 0ms render)
            liked_tracks = self._settings.get_liked_tracks() if self._settings else []
            light_tracks = [self._clone_track_lightweight(t) for t in liked_tracks]
            self.tracks_loaded.emit(FAVORITES_CHAT_ID, light_tracks, False)

            # Phase 2: Smooth progressive 1-by-1 HD cover cascade
            self._start_staggered_covers(liked_tracks, clear_existing=True)

            # Phase 3: Live reaction sync from Telegram servers
            self.sync_favorites_from_telegram()
            return

        if reset:
            self._open_chat(chat_id)
        self._tracks.load_chat_tracks(chat_id, reset=reset, chunk_size=chunk_size)

    def load_more_tracks(self, chat_id: int) -> None:
        if chat_id == FAVORITES_CHAT_ID:
            return
        self._tracks.load_chat_tracks(chat_id, reset=False)

    @Slot(str, str)
    def search_tracks(self, chat_id_str: str, query: str) -> None:
        try:
            cid = int(chat_id_str)
            if cid == FAVORITES_CHAT_ID:
                if self._settings:
                    liked = self._settings.get_liked_tracks()
                    q = query.strip().lower()
                    filtered = [
                        t for t in liked
                        if q in t.display_title.lower() or q in t.display_artist.lower()
                    ]
                    self.search_results_received.emit(FAVORITES_CHAT_ID, filtered, False)
                    self._start_staggered_covers(filtered, clear_existing=True)
                else:
                    self.search_results_received.emit(FAVORITES_CHAT_ID, [], False)
                return

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
        self._clear_cover_queue()
        self._connection.stop()
        self._adapter.send({"@type": "logOut"})

    def stop(self) -> None:
        self._net_timer.stop()
        self._clear_cover_queue()
        self._connection.stop()
        if self._worker:
            self._worker.stop()
            self._worker = None