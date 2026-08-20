from typing import Any

HEART_EMOJIS = frozenset({"❤", "♥", "❤️"})


def extract_heart_reaction(message_or_info: dict[str, Any] | None) -> tuple[bool, int]:
    """Extract heart reaction status and total count from message metadata."""
    if not message_or_info:
        return False, 0

    info = message_or_info.get("interaction_info")
    if info is None and message_or_info.get("@type") == "messageInteractionInfo":
        info = message_or_info

    reactions_data = (
        info.get("reactions")
        if isinstance(info, dict)
        else message_or_info.get("reactions")
    )

    if not isinstance(reactions_data, dict):
        return False, 0

    reactions_list = reactions_data.get("reactions", [])
    if not isinstance(reactions_list, list):
        return False, 0

    for reaction in reactions_list:
        if not isinstance(reaction, dict):
            continue
        r_type = reaction.get("type", {})
        if not isinstance(r_type, dict):
            continue

        raw_emoji = str(r_type.get("emoji", "")).replace("\ufe0f", "")
        if raw_emoji in HEART_EMOJIS:
            count = reaction.get("total_count", 0)
            is_liked = bool(reaction.get("is_chosen", False))
            return is_liked, count

    return False, 0