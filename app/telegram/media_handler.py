import logging
from pathlib import Path
from typing import Any, Callable

from app.telegram.adapter import TDLibAdapter

logger = logging.getLogger("tmusic.telegram.media")


class MediaHandler:
    """Manages audio file streaming downloads, HD cover art, and path registry."""

    def __init__(
        self,
        adapter: TDLibAdapter,
        on_audio_progress: Callable[[int, int, int], None],
        on_audio_completed: Callable[[int, str], None],
        on_cover_completed: Callable[[str, str], None],
    ) -> None:
        self._adapter = adapter
        self._on_audio_progress = on_audio_progress
        self._on_audio_completed = on_audio_completed
        self._on_cover_completed = on_cover_completed

        self._file_id_to_path: dict[int, str] = {}
        self._downloading_audio_files: set[int] = set()
        self._cover_file_to_track_id: dict[int, str] = {}

    def get_downloaded_path(self, file_id: int) -> str | None:
        path = self._file_id_to_path.get(file_id)
        if path and Path(path).exists():
            return path
        return None

    def register_completed_path(self, file_id: int, path: str) -> None:
        """Register or update active valid path for a file ID."""
        if path and Path(path).exists():
            self._file_id_to_path[file_id] = path

    def download_audio_file(self, file_id: int) -> None:
        if file_id in self._file_id_to_path and Path(self._file_id_to_path[file_id]).exists():
            self._on_audio_completed(file_id, self._file_id_to_path[file_id])
            return

        self._downloading_audio_files.add(file_id)
        logger.info("Requesting TDLib download for file ID: %d", file_id)
        self._adapter.send({
            "@type": "downloadFile",
            "file_id": file_id,
            "priority": 32,
            "offset": 0,
            "limit": 0,
            "synchronous": False,
        })

    def prefetch_audio_file(self, file_id: int) -> None:
        if file_id in self._file_id_to_path and Path(self._file_id_to_path[file_id]).exists():
            return

        self._downloading_audio_files.add(file_id)
        logger.info("⚡ Smart Pre-fetching track file ID: %d", file_id)
        self._adapter.send({
            "@type": "downloadFile",
            "file_id": file_id,
            "priority": 16,
            "offset": 0,
            "limit": 0,
            "synchronous": False,
        })

    def download_cover_file(self, track_id: str, file_id: int) -> None:
        if not file_id:
            return

        self._cover_file_to_track_id[file_id] = track_id

        if file_id in self._file_id_to_path and Path(self._file_id_to_path[file_id]).exists():
            self._on_cover_completed(track_id, self._file_id_to_path[file_id])
            return

        self._adapter.send({
            "@type": "downloadFile",
            "file_id": file_id,
            "priority": 4,
            "offset": 0,
            "limit": 0,
            "synchronous": False,
        })

    def process_file_update(self, file_obj: dict[str, Any]) -> None:
        file_id = file_obj.get("id", 0)
        local = file_obj.get("local", {})
        is_completed = local.get("is_downloading_completed", False)
        path = local.get("path", "")
        downloaded = local.get("downloaded_size", 0)
        total = file_obj.get("size", 0) or file_obj.get("expected_size", 0)

        if is_completed and path:
            self._file_id_to_path[file_id] = path

            # 1. HD cover art check
            track_id = self._cover_file_to_track_id.get(file_id)
            if track_id:
                self._on_cover_completed(track_id, path)

            # 2. Audio track completion notification
            self._downloading_audio_files.discard(file_id)
            self._on_audio_completed(file_id, path)

        elif local.get("is_downloading_active", False):
            self._on_audio_progress(file_id, downloaded, total)