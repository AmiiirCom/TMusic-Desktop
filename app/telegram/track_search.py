from dataclasses import dataclass
import logging
from typing import Any, Callable

from app.models.track import Track
from app.telegram.adapter import TDLibAdapter

logger = logging.getLogger("tmusic.telegram.track_search")


@dataclass(slots=True)
class SearchState:
    """State tracking for multi-page audio message searches within a chat."""

    chat_id: int
    query: str
    accumulated_tracks: list[Track]
    next_from_message_id: int
    is_complete: bool
    extra_id: str
    limit: int = 100


class TrackSearchHandler:
    """Handles deep multi-page track searches inside Telegram chats."""

    def __init__(
        self,
        adapter: TDLibAdapter,
        parse_messages: Callable[[int, list[dict[str, Any]]], list[Track]],
        on_search_results: Callable[[int, list[Track], bool], None],
    ) -> None:
        self._adapter = adapter
        self._parse_messages = parse_messages
        self._on_search_results = on_search_results
        self._search_states: dict[int, SearchState] = {}

    def search_tracks(self, chat_id: int, query: str, limit: int = 100) -> None:
        if not query.strip():
            return

        extra_id = f"search_tracks_{chat_id}_{id(self)}_{len(self._search_states)}"
        self._search_states[chat_id] = SearchState(
            chat_id=chat_id,
            query=query,
            accumulated_tracks=[],
            next_from_message_id=0,
            is_complete=False,
            extra_id=extra_id,
            limit=limit,
        )

        self._send_search_request(chat_id, query, 0, extra_id, limit)

    def _send_search_request(
        self, chat_id: int, query: str, from_msg_id: int, extra_id: str, limit: int
    ) -> None:
        self._adapter.send({
            "@type": "searchChatMessages",
            "chat_id": chat_id,
            "query": query,
            "from_message_id": from_msg_id,
            "offset": 0,
            "limit": limit,
            "filter": {"@type": "searchMessagesFilterAudio"},
            "@extra": extra_id,
        })

    def process_search_page(
        self,
        chat_id: int,
        messages: list[dict[str, Any]],
        next_from_id: int,
        limit: int,
        extra: str,
    ) -> None:
        search_state = self._search_states.get(chat_id)
        if not search_state or search_state.extra_id != extra:
            return

        chunk = self._parse_messages(chat_id, messages)
        search_state.accumulated_tracks.extend(chunk)

        if next_from_id != 0 and messages:
            self._send_search_request(chat_id, search_state.query, next_from_id, extra, limit)
        else:
            search_state.is_complete = True
            self._on_search_results(chat_id, search_state.accumulated_tracks, False)
            self._search_states.pop(chat_id, None)