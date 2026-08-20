from dataclasses import dataclass
import datetime
from pathlib import Path


@dataclass(slots=True, frozen=True)
class Track:
    """Domain model representing a music track with HD cover artwork and release date."""

    id: str  # Unique identifier: "{chat_id}_{message_id}"
    chat_id: int
    message_id: int
    file_id: int
    title: str
    artist: str
    duration_seconds: int
    size_bytes: int
    file_name: str
    mime_type: str = "audio/mpeg"
    local_path: str | None = None
    is_downloaded: bool = False
    date_timestamp: int = 0
    minithumbnail_data: bytes | None = None
    cover_file_id: int = 0
    cover_path: str | None = None
    is_liked: bool = False
    heart_count: int = 0

    @property
    def formatted_duration(self) -> str:
        minutes = self.duration_seconds // 60
        seconds = self.duration_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    @property
    def formatted_size(self) -> str:
        if self.size_bytes < 1024 * 1024:
            return f"{self.size_bytes / 1024:.1f} KB"
        return f"{self.size_bytes / (1024 * 1024):.1f} MB"

    @property
    def formatted_date(self) -> str:
        if not self.date_timestamp:
            return ""
        dt = datetime.datetime.fromtimestamp(self.date_timestamp)
        return dt.strftime("%Y/%m/%d")

    @property
    def display_title(self) -> str:
        if self.title.strip():
            return self.title.strip()
        return Path(self.file_name).stem if self.file_name else "Unknown Track"

    @property
    def display_artist(self) -> str:
        return self.artist.strip() if self.artist.strip() else "Unknown Artist"