from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class Track:
    """Domain model representing a music track from Telegram."""

    id: str  # Unique identifier: "{chat_id}_{message_id}"
    chat_id: int
    message_id: int
    file_id: int  # TDLib file ID for download/playback
    title: str
    artist: str
    duration_seconds: int
    size_bytes: int
    file_name: str
    mime_type: str = "audio/mpeg"
    local_path: str | None = None
    is_downloaded: bool = False

    @property
    def formatted_duration(self) -> str:
        """Format seconds into MM:SS (e.g. 03:45)."""
        minutes = self.duration_seconds // 60
        seconds = self.duration_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    @property
    def formatted_size(self) -> str:
        """Format bytes into readable MB/KB string."""
        if self.size_bytes < 1024 * 1024:
            return f"{self.size_bytes / 1024:.1f} KB"
        return f"{self.size_bytes / (1024 * 1024):.1f} MB"

    @property
    def display_title(self) -> str:
        if self.title.strip():
            return self.title.strip()
        # Fallback to filename without extension
        return Path(self.file_name).stem if self.file_name else "Unknown Track"

    @property
    def display_artist(self) -> str:
        return self.artist.strip() if self.artist.strip() else "Unknown Artist"