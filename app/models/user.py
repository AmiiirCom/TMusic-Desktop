from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class TelegramUser:
    """Domain model representing the authenticated Telegram user with cached avatar."""

    id: int
    first_name: str
    last_name: str = ""
    username: str = ""
    phone_number: str = ""
    photo_id: int = 0  # Unique Telegram profile photo version identifier
    photo_file_id: int = 0
    photo_path: str | None = None
    minithumb_data: bytes | None = None

    @property
    def full_name(self) -> str:
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name

    @property
    def initial_letter(self) -> str:
        if self.first_name:
            return self.first_name[0].upper()
        return "U"