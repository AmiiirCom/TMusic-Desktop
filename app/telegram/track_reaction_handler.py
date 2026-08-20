import logging
from typing import Any, Callable

from app.telegram.adapter import TDLibAdapter
from app.telegram.reactions import extract_heart_reaction

logger = logging.getLogger("tmusic.telegram.track_reactions")


class TrackReactionHandler:
    """Manages Telegram message heart reactions, optimistic updates, and rollbacks."""

    def __init__(
        self,
        adapter: TDLibAdapter,
        update_track_reaction_callback: Callable[[int, int, bool, int], None],
        on_track_reaction_updated: Callable[[int, int, bool, int], None],
    ) -> None:
        self._adapter = adapter
        self._update_track_reaction = update_track_reaction_callback
        self._on_track_reaction_updated = on_track_reaction_updated

    def toggle_track_like(self, chat_id: int, message_id: int, current_liked: bool) -> None:
        if not self._adapter.is_loaded:
            return

        extra = f"react_{chat_id}_{message_id}_{0 if current_liked else 1}"
        action = "removeMessageReaction" if current_liked else "addMessageReaction"
        payload = {
            "@type": action,
            "chat_id": chat_id,
            "message_id": message_id,
            "reaction_type": {"@type": "reactionTypeEmoji", "emoji": "❤"},
            "@extra": extra,
        }
        if not current_liked:
            payload["is_big"] = False
            payload["update_recent_reactions"] = True

        self._adapter.send(payload)

    def revert_track_reaction(self, chat_id: int, message_id: int, original_liked: bool) -> None:
        self._update_track_reaction(chat_id, message_id, original_liked, -1)

    def process_interaction_info_update(
        self, chat_id: int, message_id: int, interaction_info: dict[str, Any] | None
    ) -> None:
        is_liked, count = extract_heart_reaction({"interaction_info": interaction_info} if interaction_info else {})
        self._update_track_reaction(chat_id, message_id, is_liked, count)
        self._on_track_reaction_updated(chat_id, message_id, is_liked, count)

    def process_reactions_update(
        self, chat_id: int, message_id: int, reactions_obj: dict[str, Any] | None
    ) -> None:
        is_liked, count = extract_heart_reaction({"reactions": reactions_obj} if reactions_obj else {})
        self._update_track_reaction(chat_id, message_id, is_liked, count)
        self._on_track_reaction_updated(chat_id, message_id, is_liked, count)