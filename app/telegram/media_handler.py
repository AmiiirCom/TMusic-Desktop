import base64
from collections import defaultdict
import logging
from pathlib import Path
from typing import Any, Callable

from app.core.image_compressor import compress_image, get_compressed_image_path
from app.telegram.adapter import TDLibAdapter

logger = logging.getLogger("tmusic.telegram.media")

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')


class MediaHandler:
    """Manages audio file streaming downloads, HD cover art, and collision-free completion dispatching."""

    def __init__(
        self,
        adapter: TDLibAdapter,
        config: Any,  # AppConfig
        cache_manager: Any,  # CacheManager
        on_audio_progress: Callable[[int, int, int], None],
        on_audio_completed: Callable[[int, str], None],
        on_cover_completed: Callable[[str, str], None],
    ) -> None:
        self._adapter = adapter
        self._config = config
        self._cache = cache_manager
        self._on_audio_progress = on_audio_progress
        self._on_audio_completed = on_audio_completed
        self._on_cover_completed = on_cover_completed

        self._file_id_to_path: dict[int, str] = {}
        self._downloading_audio_files: set[int] = set()
        # Map each cover file_id to a set of track_ids (handles shared album/channel artwork)
        self._cover_file_to_track_ids: dict[int, set[str]] = defaultdict(set)

    @property
    def has_active_downloads(self) -> bool:
        return bool(self._downloading_audio_files or self._cover_file_to_track_ids)

    def get_downloaded_path(self, file_id: int) -> str | None:
        path = self._file_id_to_path.get(file_id)
        if path:
            p = Path(path)
            if p.is_file():
                return path
        return None

    def register_completed_path(self, file_id: int, path: str) -> None:
        if path:
            p = Path(path)
            if p.is_file():
                self._file_id_to_path[file_id] = path

    def download_audio_file(self, file_id: int) -> None:
        """Download with MAXIMUM priority (32) for immediate playback and export."""
        existing = self.get_downloaded_path(file_id)
        if existing:
            self._on_audio_completed(file_id, existing)
            return

        self._downloading_audio_files.add(file_id)
        logger.debug("Requesting immediate TDLib download for file ID: %d (Priority 32)", file_id)
        self._adapter.send({
            "@type": "downloadFile",
            "file_id": file_id,
            "priority": 32,
            "offset": 0,
            "limit": 0,
            "synchronous": False,
        })

    def prefetch_audio_file(self, file_id: int) -> None:
        """Pre-download upcoming track with background priority (16)."""
        if self.get_downloaded_path(file_id):
            return

        self._downloading_audio_files.add(file_id)
        logger.debug("Smart Pre-fetching track file ID: %d", file_id)
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

        self._cover_file_to_track_ids[file_id].add(track_id)

        existing = self.get_downloaded_path(file_id)
        if existing:
            self._on_cover_completed(track_id, existing)
            return

        self._adapter.send({
            "@type": "downloadFile",
            "file_id": file_id,
            "priority": 16,
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
            file_path = Path(path)

            # Check if this file is registered as a cover image
            track_ids = self._cover_file_to_track_ids.pop(file_id, set())
            if track_ids:
                final_path_str = path
                if file_path.is_file():
                    # Name cached cover by its unique file_id to avoid track_id conflicts
                    compressed_path = get_compressed_image_path(
                        self._config.thumb_cache_dir,
                        "cover",
                        str(file_id)
                    )
                    result = compress_image(file_path, compressed_path)
                    if result:
                        self._cache.add_file(file_id, result, file_type="thumb")
                        self._delete_from_tdlib(file_id)
                        final_path_str = str(result)
                    else:
                        self._cache.add_file(file_id, file_path, file_type="thumb")

                # Accurately dispatch to all tracks that share this cover
                for tid in track_ids:
                    self._on_cover_completed(tid, final_path_str)
                return

            # Explicitly ignore non-audio image files (avatars, previews)
            if file_path.suffix.lower() in IMAGE_EXTENSIONS:
                return

            # Otherwise, treat as audio file -> trigger export to TMusicDownloads
            self._downloading_audio_files.discard(file_id)
            logger.debug("Audio file ID %d 100%% complete in TDLib -> Triggering immediate export: %s", file_id, path)
            self._on_audio_completed(file_id, path)

        elif local.get("is_downloading_active", False):
            self._on_audio_progress(file_id, downloaded, total)

    def _delete_from_tdlib(self, file_id: int) -> None:
        """Send deleteFile request to TDLib."""
        if not self._adapter.is_loaded:
            return
        try:
            self._adapter.send({
                "@type": "deleteFile",
                "file_id": file_id,
            })
            logger.debug("Sent deleteFile request to TDLib for file_id=%d", file_id)
        except Exception as exc:
            logger.warning("Failed to send deleteFile to TDLib: %s", exc)