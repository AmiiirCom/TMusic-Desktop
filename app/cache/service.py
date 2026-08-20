import json
import logging
import threading
from pathlib import Path
import shutil
import time
from typing import Any, Optional

from app.config import AppConfig
from app.core.security import CryptoManager
from app.telegram.adapter import TDLibAdapter

logger = logging.getLogger("tmusic.cache.manager")

# Maximum total cache size (audio + thumbnails) in bytes
MAX_CACHE_SIZE_BYTES = 1024 * 1024 * 1024  # 1 GiB

# Incomplete file cleanup: delete if older than this many seconds
INCOMPLETE_FILE_MAX_AGE_SECONDS = 24 * 3600  # 24 hours


class CacheManager:
    """
    Centralised cache manager with:
    - Automatic size enforcement (LRU eviction based on last access time)
    - Metadata persistence (encrypted)
    - Incomplete file cleanup
    - Thread-safe operations
    - TDLib integration for file deletion
    """

    def __init__(self, config: AppConfig, crypto: CryptoManager, adapter: TDLibAdapter) -> None:
        self._config = config
        self._crypto = crypto
        self._adapter = adapter
        self._lock = threading.RLock()

        # In-memory metadata: {file_id: {"path": str, "last_access": float, "size": int, "type": "audio"|"thumb"}}
        self._metadata: dict[int, dict[str, Any]] = {}
        self._load_metadata()

        # Start periodic cleanup for incomplete files (every hour)
        self._start_cleanup_timer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_file(self, file_id: int, local_path: Path, file_type: str = "audio") -> None:
        """
        Register a newly downloaded/cached file.
        If the file exists, its last_access is updated.
        """
        if not local_path.exists():
            logger.debug("Cannot add missing file: %s", local_path)
            return

        with self._lock:
            # Remove any existing entry for this file_id (in case of overwrite)
            self._remove_entry(file_id, update_disk=False)

            size = local_path.stat().st_size
            self._metadata[file_id] = {
                "path": str(local_path),
                "last_access": time.time(),
                "size": size,
                "type": file_type,
            }
            self._save_metadata()
            logger.debug("Added cache entry: file_id=%d, path=%s, size=%d", file_id, local_path, size)

            # Enforce size limit after adding
            self._enforce_size_limit()

    def get_file_path(self, file_id: int) -> Optional[Path]:
        """
        Retrieve the cached path for a file_id.
        Updates last_access time if found.
        Returns None if not found or file missing.
        """
        with self._lock:
            entry = self._metadata.get(file_id)
            if not entry:
                return None

            path = Path(entry["path"])
            if not path.exists():
                # Stale entry: remove and return None
                self._remove_entry(file_id, update_disk=True)
                return None

            # Update last access time
            entry["last_access"] = time.time()
            self._save_metadata()
            return path

    def remove_file(self, file_id: int, delete_from_tdlib: bool = True) -> bool:
        """
        Remove a cached file from disk and metadata.
        If delete_from_tdlib is True, also ask TDLib to forget the file.
        Returns True if the file was removed (or didn't exist).
        """
        with self._lock:
            entry = self._metadata.pop(file_id, None)
            if entry:
                path = Path(entry["path"])
                if path.exists():
                    try:
                        path.unlink(missing_ok=True)
                        logger.debug("Removed cached file: %s (file_id=%d)", path, file_id)
                    except Exception as exc:
                        logger.warning("Failed to delete cache file %s: %s", path, exc)

                # Save metadata after removal
                self._save_metadata()

            if delete_from_tdlib and self._adapter.is_loaded:
                self._delete_from_tdlib(file_id)

            return True

    def cleanup_incomplete_files(self) -> None:
        """
        Scan the TDLib files directory and remove files that are incomplete
        and older than INCOMPLETE_FILE_MAX_AGE_SECONDS.
        Also remove orphaned files not tracked in metadata.
        """
        with self._lock:
            td_files_dir = self._config.tdlib_files_dir
            if not td_files_dir.exists():
                return

            now = time.time()
            removed = 0
            for item in td_files_dir.glob("*"):
                if item.is_file():
                    # Check if this file is tracked in metadata
                    tracked = False
                    for entry in self._metadata.values():
                        if Path(entry["path"]) == item:
                            tracked = True
                            break

                    if not tracked:
                        # Orphaned file: remove
                        try:
                            item.unlink(missing_ok=True)
                            removed += 1
                            logger.debug("Removed orphaned cache file: %s", item)
                        except Exception as exc:
                            logger.warning("Could not remove orphaned file %s: %s", item, exc)
                        continue

            if removed:
                logger.info("Cleaned up %d orphaned/incomplete cache files.", removed)

    def clear_all(self) -> None:
        """Delete all cached files and reset metadata."""
        with self._lock:
            # Remove all files from disk
            for entry in self._metadata.values():
                path = Path(entry["path"])
                try:
                    if path.exists():
                        path.unlink(missing_ok=True)
                except Exception:
                    pass
            self._metadata.clear()
            self._save_metadata()

            # Also clear TDLib's file cache directory
            for dir_path in (self._config.tdlib_files_dir, self._config.thumb_cache_dir):
                if dir_path.exists():
                    for item in dir_path.glob("*"):
                        try:
                            if item.is_file():
                                item.unlink(missing_ok=True)
                            elif item.is_dir():
                                shutil.rmtree(item, ignore_errors=True)
                        except Exception as exc:
                            logger.warning("Could not delete %s: %s", item, exc)

            logger.info("Cleared all cache.")

    def get_total_size(self) -> int:
        """Calculate total size of all cached files tracked in metadata."""
        with self._lock:
            total = 0
            for entry in self._metadata.values():
                total += entry.get("size", 0)
            return total

    def get_formatted_size(self) -> str:
        size = self.get_total_size()
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    def get_formatted_max_size(self) -> str:
        """Return formatted maximum cache size limit."""
        if MAX_CACHE_SIZE_BYTES < 1024 * 1024:
            return f"{MAX_CACHE_SIZE_BYTES / 1024:.0f} KB"
        elif MAX_CACHE_SIZE_BYTES < 1024 * 1024 * 1024:
            return f"{MAX_CACHE_SIZE_BYTES / (1024 * 1024):.0f} MB"
        else:
            return f"{MAX_CACHE_SIZE_BYTES / (1024 * 1024 * 1024):.0f} GiB"

    def get_downloads_size(self, downloads_dir: Path | None = None) -> int:
        """Calculate size of user downloads folder. If directory is not provided, use config default."""
        target = downloads_dir or self._config.downloads_dir
        if not target.exists():
            return 0
        total = 0
        for item in target.rglob("*"):
            if item.is_file():
                try:
                    total += item.stat().st_size
                except OSError:
                    pass
        return total

    def get_formatted_downloads_size(self, downloads_dir: Path | None = None) -> str:
        size = self.get_downloads_size(downloads_dir)
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------

    def _load_metadata(self) -> None:
        """Load encrypted metadata from disk."""
        meta_file = self._config.metadata_file
        if not meta_file.exists():
            self._metadata = {}
            return

        try:
            data = self._crypto.load_encrypted_json(meta_file)
            if data and isinstance(data, dict):
                # Convert keys to int
                self._metadata = {int(k): v for k, v in data.items()}
                logger.debug("Loaded cache metadata for %d files.", len(self._metadata))
            else:
                self._metadata = {}
        except Exception as exc:
            logger.warning("Failed to load cache metadata: %s", exc)
            self._metadata = {}

    def _save_metadata(self) -> None:
        """Save encrypted metadata to disk."""
        meta_file = self._config.metadata_file
        try:
            # Convert int keys to str for JSON
            data = {str(k): v for k, v in self._metadata.items()}
            self._crypto.save_encrypted_json(meta_file, data)
        except Exception as exc:
            logger.error("Failed to save cache metadata: %s", exc)

    def _remove_entry(self, file_id: int, update_disk: bool = True) -> None:
        """Remove a metadata entry and optionally delete the file."""
        entry = self._metadata.pop(file_id, None)
        if entry and update_disk:
            path = Path(entry["path"])
            if path.exists():
                try:
                    path.unlink(missing_ok=True)
                    logger.debug("Removed cache file during eviction: %s", path)
                except Exception as exc:
                    logger.warning("Could not delete file %s: %s", path, exc)

    def _enforce_size_limit(self) -> None:
        """Evict least-recently-used files until total size <= MAX_CACHE_SIZE_BYTES."""
        total = self.get_total_size()
        if total <= MAX_CACHE_SIZE_BYTES:
            return

        # Sort entries by last_access (oldest first)
        sorted_entries = sorted(self._metadata.items(), key=lambda kv: kv[1]["last_access"])

        evicted = 0
        freed = 0
        while total > MAX_CACHE_SIZE_BYTES and sorted_entries:
            file_id, entry = sorted_entries.pop(0)
            size = entry.get("size", 0)
            # Remove from metadata and disk
            self._remove_entry(file_id, update_disk=True)
            total -= size
            freed += size
            evicted += 1

        if evicted:
            logger.info("Evicted %d cache files (%s) to stay under %d MB limit.",
                        evicted, self._format_bytes(freed), MAX_CACHE_SIZE_BYTES // (1024*1024))
            self._save_metadata()

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

    def _start_cleanup_timer(self) -> None:
        """Start a background timer that runs cleanup_incomplete_files every hour."""
        import threading
        def cleanup_loop() -> None:
            while True:
                time.sleep(3600)  # 1 hour
                try:
                    self.cleanup_incomplete_files()
                except Exception as exc:
                    logger.exception("Error in cache cleanup loop: %s", exc)

        thread = threading.Thread(target=cleanup_loop, daemon=True, name="CacheCleanup")
        thread.start()
        logger.info("Cache cleanup thread started (runs every hour).")

    @staticmethod
    def _format_bytes(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"