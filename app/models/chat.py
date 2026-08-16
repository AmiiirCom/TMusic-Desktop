from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class OwnedChat:
    id: int
    title: str
    is_channel: bool
    supergroup_id: int = 0
    unread_count: int = 0

    @property
    def type_display(self) -> str:
        return "کانال" if self.is_channel else "سوپرگروه"