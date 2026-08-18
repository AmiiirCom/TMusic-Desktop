import base64
from dataclasses import dataclass, field
import logging
from typing import Any, Callable

from app.models.track import Track
from app.telegram.adapter import TDLibAdapter

logger = logging.getLogger("tmusic.telegram.tracks")


@dataclass(slots=True)
class ChatTrackPaginationState:
    chat_id: int
    tracks: list[Track] = field(default_factory=list)
    next_from_message_id: int = 0
    is_loading: bool = False
    has_more: bool = True


class TrackHandler:
    """Event-driven audio track manager responding in real-time to TDLib updates."""

    def __init__(
        self,
        adapter: TDLibAdapter,
        request_cover_download: Callable[[str, int], None],
        register_file_path: Callable[[int, str], None],
        on_initial_chunk_loaded: Callable[[int, list[Track], bool], None],
        on_lazy_chunk_appended: Callable[[int, list[Track], bool], None],
        on_delta_tracks_prepended: Callable[[int, list[Track]], None],
        on_tracks_deleted: Callable[[int, list[str]], None],
    ) -> None:
        self._adapter = adapter
        self._request_cover_download = request_cover_download
        self._register_file_path = register_file_path
        self._on_initial_chunk_loaded = on_initial_chunk_loaded
        self._on_lazy_chunk_appended = on_lazy_chunk_appended
        self._on_delta_tracks_prepended = on_delta_tracks_prepended
        self._on_tracks_deleted = on_tracks_deleted

        self._track_pagination: dict[int, ChatTrackPaginationState] = {}

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

    def process_new_message(self, message: dict[str, Any]) -> None:
        """Real-time event: React immediately when a new audio track is posted in Telegram."""
        chat_id = message.get("chat_id", 0)
        state = self._track_pagination.get(chat_id)
        if not state:
            return

        parsed_tracks = self._parse_message_tracks(chat_id, [message])
        if not parsed_tracks:
            return

        new_track = parsed_tracks[0]
        existing_ids = {t.id for t in state.tracks}

        if new_track.id not in existing_ids:
            logger.info("⚡ Live Push Event: New track posted in chat %d -> %s", chat_id, new_track.display_title)
            state.tracks.insert(0, new_track)
            self._on_delta_tracks_prepended(chat_id, [new_track])

    def process_delete_messages(self, chat_id: int, message_ids: list[int]) -> None:
        """Real-time event: React immediately when tracks are deleted in Telegram."""
        state = self._track_pagination.get(chat_id)
        if not state or not state.tracks:
            return

        del_track_ids = {f"{chat_id}_{mid}" for mid in message_ids}
        original_count = len(state.tracks)
        state.tracks = [t for t in state.tracks if t.id not in del_track_ids]

        if len(state.tracks) < original_count:
            logger.info("🗑️ Live Push Event: Removed %d deleted tracks from chat %d", original_count - len(state.tracks), chat_id)
            self._on_tracks_deleted(chat_id, list(del_track_ids))

    def _parse_message_tracks(self, chat_id: int, messages: list[dict[str, Any]]) -> list[Track]:
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
                        self._request_cover_download(track_id, cover_file_id)

                if local_file.get("is_downloading_completed") and path:
                    self._register_file_path(file_id, path)

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
                    local_path=path if local_file.get("is_downloading_completed") else None,
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
                            self._request_cover_download(track_id, cover_file_id)

                    if local_file.get("is_downloading_completed") and path:
                        self._register_file_path(file_id, path)

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
                        local_path=path if local_file.get("is_downloading_completed") else None,
                        is_downloaded=local_file.get("is_downloading_completed", False),
                        date_timestamp=msg_date,
                        minithumbnail_data=minithumb_data,
                        cover_file_id=cover_file_id,
                        cover_path=cover_path,
                    )
                    chunk_tracks.append(track)
        return chunk_tracks

    def process_search_response(
        self, chat_id: int, messages: list[dict[str, Any]], next_from_id: int, is_initial: bool
    ) -> None:
        state = self._track_pagination.get(chat_id)
        if not state:
            state = ChatTrackPaginationState(chat_id=chat_id)
            self._track_pagination[chat_id] = state

        state.is_loading = False
        state.next_from_message_id = next_from_id
        state.has_more = (next_from_id != 0) and (len(messages) > 0)

        chunk_tracks = self._parse_message_tracks(chat_id, messages)

        if is_initial:
            state.tracks = list(chunk_tracks)
            self._on_initial_chunk_loaded(chat_id, state.tracks, state.has_more)
        else:
            state.tracks.extend(chunk_tracks)
            self._on_lazy_chunk_appended(chat_id, chunk_tracks, state.has_more)