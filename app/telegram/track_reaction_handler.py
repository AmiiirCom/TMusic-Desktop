import logging
from typing import Any, Callable

from app.telegram.adapter import TDLibAdapter
from app.telegram.reactions import extract_heart_reaction

logger = logging.getLogger("tmusic.telegram.track_reactions")


class TrackReactionHandler:
    """Manages Telegram message heart reactions, standalone album copies, and rollbacks."""

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
        """Send direct reaction to Telegram message via TDLib."""
        if not self._adapter.is_loaded or chat_id == 0 or message_id == 0:
            return

        # Ensure TDLib has viewed the message so reaction is accepted
        try:
            self._adapter.send({
                "@type": "viewMessages",
                "chat_id": chat_id,
                "message_ids": [message_id],
                "force_read": False,
            })
        except Exception:
            pass

        extra = f"react_{chat_id}_{message_id}_{0 if current_liked else 1}"
        action = "removeMessageReaction" if current_liked else "addMessageReaction"

        # Canonical TDLib red heart emoji string without variation selector
        payload: dict[str, Any] = {
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
        logger.info("Sent TDLib %s (chat_id=%d, message_id=%d)", action, chat_id, message_id)

    def forward_copy_and_like(self, chat_id: int, message_id: int, extra: str) -> None:
        """Forward single track from album without sender header (send_copy) into the same chat."""
        if not self._adapter.is_loaded or chat_id == 0 or message_id == 0:
            return

        self._adapter.send({
            "@type": "forwardMessages",
            "chat_id": chat_id,
            "from_chat_id": chat_id,
            "message_ids": [message_id],
            "send_copy": True,
            "remove_caption": False,
            "@extra": extra,
        })
        logger.info("Forwarding album track %d as standalone copy into chat %d (extra=%s)", message_id, chat_id, extra)

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