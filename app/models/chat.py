from dataclasses import dataclass
from PySide6.QtCore import QCoreApplication

FAVORITES_CHAT_ID: int = -999999


@dataclass(slots=True, frozen=True)
class OwnedChat:
    id: int
    title: str
    is_channel: bool
    supergroup_id: int = 0
    unread_count: int = 0

    @property
    def is_favorites(self) -> bool:
        return self.id == FAVORITES_CHAT_ID

    @property
    def type_display(self) -> str:
        if self.is_favorites:
            return QCoreApplication.translate("OwnedChat", "Favorites")
        if self.is_channel:
            return QCoreApplication.translate("OwnedChat", "Channel")
        return QCoreApplication.translate("OwnedChat", "Supergroup")


def get_favorites_chat() -> OwnedChat:
    """Create the pinned singleton Favorites chat entry."""
    return OwnedChat(
        id=FAVORITES_CHAT_ID,
        title=QCoreApplication.translate("OwnedChat", "Favorites"),
        is_channel=False,
        supergroup_id=0,
        unread_count=0,
    )