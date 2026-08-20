from typing import Any

# Comprehensive list of Telegram heart reaction variants
HEART_EMOJIS = frozenset({
    "❤", "♥", "❤️", "💖", "💗", "💓", "💞", "💕", "💘",
    "🖤", "🤍", "🤎", "💜", "💙", "💚", "💛", "🧡", "🫀",
})


def extract_heart_reaction(message_or_info: dict[str, Any] | None) -> tuple[bool, int]:
    """
    Extract heart reaction status strictly chosen by the CURRENT authenticated user
    (is_chosen == True) and the total heart reaction count.
    
    If other users liked the message but the current user did not, is_liked will be False.
    """
    if not message_or_info or not isinstance(message_or_info, dict):
        return False, 0

    # Extract interaction info or reactions object from any TDLib response envelope
    info = message_or_info.get("interaction_info")
    if info is None and message_or_info.get("@type") == "messageInteractionInfo":
        info = message_or_info
    elif info is None and message_or_info.get("@type") == "messageReactions":
        info = {"reactions": message_or_info}
    elif info is None:
        info = message_or_info

    reactions_data = (
        info.get("reactions")
        if isinstance(info, dict)
        else message_or_info.get("reactions")
    )

    if isinstance(reactions_data, list):
        reactions_list = reactions_data
    elif isinstance(reactions_data, dict):
        reactions_list = reactions_data.get("reactions", [])
    else:
        reactions_list = []

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
            count = int(reaction.get("total_count", 0))
            # STRICT: is_chosen is True ONLY if the current authenticated user added this reaction
            is_chosen_by_me = bool(reaction.get("is_chosen", False))
            return is_chosen_by_me, count

    return False, 0