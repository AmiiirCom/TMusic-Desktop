from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class TelegramUser:
    id: int
    first_name: str
    last_name: str = ""
    username: str = ""
    phone_number: str = ""

    @property
    def full_name(self) -> str:
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name