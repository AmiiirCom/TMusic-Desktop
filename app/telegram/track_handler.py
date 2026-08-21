from dataclasses import dataclass, field
import logging
from typing import Any, Callable

from app.models.track import Track
from app.telegram.adapter import TDLibAdapter
from app.telegram.track_parser import parse_message_to_track
from app.telegram.track_reaction_handler import TrackReactionHandler
from app.telegram.track_search import TrackSearchHandler

logger = logging.getLogger("tmusic.telegram.tracks")


@dataclass(slots=True)
class ChatTrackPaginationState:
    chat_id: int
    tracks: list[Track] = field(default_factory=list)
    next_from_message_id: int = 0
    is_loading: bool = False
    has_more: bool = True
    search_query: str = ""


class TrackHandler:
    """Manages audio track pagination, message streams, search, and reactions."""

    def __init__(
        self,
        adapter: TDLibAdapter,
        request_cover_download: Callable[[str, int], None],
        register_file_path: Callable[[int, str], None],
        on_initial_chunk_loaded: Callable[[int, list[Track], bool], None],
        on_lazy_chunk_appended: Callable[[int, list[Track], bool], None],
        on_delta_tracks_prepended: Callable[[int, list[Track]], None],
        on_tracks_deleted: Callable[[int, list[str]], None],
        on_search_results: Callable[[int, list[Track], bool], None],
        on_track_reaction_updated: Callable[[int, int, bool, int], None],
    ) -> None:
        self._adapter = adapter
        self._request_cover_download = request_cover_download
        self._register_file_path = register_file_path
        self._on_initial_chunk_loaded = on_initial_chunk_loaded
        self._on_lazy_chunk_appended = on_lazy_chunk_appended
        self._on_delta_tracks_prepended = on_delta_tracks_prepended
        self._on_tracks_deleted = on_tracks_deleted
        self._on_track_reaction_updated = on_track_reaction_updated

        self._track_pagination: dict[int, ChatTrackPaginationState] = {}

        self._search_handler = TrackSearchHandler(
            adapter=self._adapter,
            parse_messages=self._parse_messages,
            on_search_results=on_search_results,
        )

        self._reaction_handler = TrackReactionHandler(
            adapter=self._adapter,
            update_track_reaction_callback=self._update_cached_track_reaction,
            on_track_reaction_updated=self._on_track_reaction_updated,
        )

    def get_track(self, chat_id: int, message_id: int) -> Track | None:
        """Lookup an existing track instance in memory."""
        state = self._track_pagination.get(chat_id)
        if state:
            for t in state.tracks:
                if t.message_id == message_id:
                    return t
        return None

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

    def search_tracks(self, chat_id: int, query: str, limit: int = 100) -> None:
        state = self._track_pagination.setdefault(chat_id, ChatTrackPaginationState(chat_id=chat_id))
        state.search_query = query.strip()
        self._search_handler.search_tracks(chat_id, query, limit)

    def process_search_page(
        self, chat_id: int, messages: list[dict[str, Any]], next_from_id: int, limit: int, extra: str
    ) -> None:
        self._search_handler.process_search_page(chat_id, messages, next_from_id, limit, extra)

    def toggle_track_like(self, chat_id: int, message_id: int, current_liked: bool) -> None:
        self._reaction_handler.toggle_track_like(chat_id, message_id, current_liked)

    def forward_copy_and_like(self, chat_id: int, message_id: int, extra: str) -> None:
        self._reaction_handler.forward_copy_and_like(chat_id, message_id, extra)

    def revert_track_reaction(self, chat_id: int, message_id: int, original_liked: bool) -> None:
        self._reaction_handler.revert_track_reaction(chat_id, message_id, original_liked)

    def process_interaction_info_update(
        self, chat_id: int, message_id: int, interaction_info: dict[str, Any] | None
    ) -> None:
        self._reaction_handler.process_interaction_info_update(chat_id, message_id, interaction_info)

    def process_reactions_update(
        self, chat_id: int, message_id: int, reactions_obj: dict[str, Any] | None
    ) -> None:
        self._reaction_handler.process_reactions_update(chat_id, message_id, reactions_obj)

    def _update_cached_track_reaction(
        self, chat_id: int, message_id: int, is_liked: bool, heart_count: int
    ) -> None:
        state = self._track_pagination.get(chat_id)
        if state:
            for idx, t in enumerate(state.tracks):
                if t.message_id == message_id:
                    new_count = heart_count if heart_count >= 0 else max(0, t.heart_count + (1 if is_liked else -1))
                    state.tracks[idx] = self._copy_track_with_like(t, is_liked, new_count)
                    break

    def process_search_response(
        self, chat_id: int, messages: list[dict[str, Any]], next_from_id: int, is_initial: bool
    ) -> None:
        state = self._track_pagination.setdefault(chat_id, ChatTrackPaginationState(chat_id=chat_id))
        state.is_loading = False
        state.next_from_message_id = next_from_id
        state.has_more = (next_from_id != 0) and bool(messages)

        chunk_tracks = self._parse_messages(chat_id, messages)
        if is_initial:
            state.tracks = list(chunk_tracks)
            self._on_initial_chunk_loaded(chat_id, state.tracks, state.has_more)
        else:
            state.tracks.extend(chunk_tracks)
            self._on_lazy_chunk_appended(chat_id, chunk_tracks, state.has_more)

    def process_new_message(self, message: dict[str, Any]) -> None:
        chat_id = message.get("chat_id", 0)
        state = self._track_pagination.get(chat_id)
        if not state:
            return

        track = parse_message_to_track(chat_id, message, self._request_cover_download, self._register_file_path)
        if not track:
            return

        existing_fps = {t.fingerprint for t in state.tracks}
        if track.fingerprint not in existing_fps and track.id not in {t.id for t in state.tracks}:
            state.tracks.insert(0, track)
            self._on_delta_tracks_prepended(chat_id, [track])

    def process_delete_messages(self, chat_id: int, message_ids: list[int]) -> None:
        state = self._track_pagination.get(chat_id)
        if not state or not state.tracks:
            return

        del_ids = {f"{chat_id}_{mid}" for mid in message_ids}
        state.tracks = [t for t in state.tracks if t.id not in del_ids]
        self._on_tracks_deleted(chat_id, list(del_ids))

    def _parse_messages(self, chat_id: int, messages: list[dict[str, Any]]) -> list[Track]:
        results: list[Track] = []
        seen_fps: set[str] = set()
        for msg in messages:
            track = parse_message_to_track(chat_id, msg, self._request_cover_download, self._register_file_path)
            if track and track.fingerprint not in seen_fps:
                seen_fps.add(track.fingerprint)
                results.append(track)
        return results
    
    def set_track_reaction_state(self, chat_id: int, message_id: int, is_liked: bool, count: int = 0) -> None:
        """Immediately update in-memory pagination cache without network delay."""
        state = self._track_pagination.get(chat_id)
        if state:
            for idx, t in enumerate(state.tracks):
                if t.message_id == message_id:
                    state.tracks[idx] = self._copy_track_with_like(t, is_liked, count)
                    break

    @staticmethod
    def _copy_track_with_like(t: Track, is_liked: bool, heart_count: int) -> Track:
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
            cover_path=t.cover_path,
            is_liked=is_liked,
            heart_count=heart_count,
            media_album_id=t.media_album_id,
            file_unique_id=t.file_unique_id,
        )