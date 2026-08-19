import logging
from pathlib import Path
import shutil

from app.config import AppConfig

logger = logging.getLogger("tmusic.cache.service")


class CacheService:
    """Manages internal cache and user-facing downloads folder."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    @property
    def downloads_path(self) -> Path:
        """Path to user-facing TMusicDownloads folder."""
        return self._config.downloads_dir

    def get_cache_size_bytes(self) -> int:
        """
        Calculate total disk usage of internal cache:
        - TDLib temporary files (data/cache)
        - Thumbnails (data/tdlib/thumbnails)
        """
        total = 0

        # 1. TDLib cache directory
        if self._config.tdlib_files_dir.exists():
            for p in self._config.tdlib_files_dir.rglob("*"):
                if p.is_file():
                    total += p.stat().st_size

        # 2. Thumbnails directory
        thumb_dir = self._config.tdlib_dir / "thumbnails"
        if thumb_dir.exists():
            for p in thumb_dir.rglob("*"):
                if p.is_file():
                    total += p.stat().st_size

        return total

    def get_formatted_cache_size(self) -> str:
        """Return formatted internal cache size."""
        size = self.get_cache_size_bytes()
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    def get_downloads_size_bytes(self) -> int:
        """Calculate total size of TMusicDownloads folder."""
        total = 0
        if self._config.downloads_dir.exists():
            for p in self._config.downloads_dir.rglob("*"):
                if p.is_file():
                    total += p.stat().st_size
        return total

    def get_formatted_downloads_size(self) -> str:
        """Return formatted TMusicDownloads size."""
        size = self.get_downloads_size_bytes()
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    def clear_cache(self) -> None:
        """
        Clear internal cache files only.
        - Removes TDLib temporary files (data/cache)
        - Removes thumbnails (data/tdlib/thumbnails)
        - Preserves TMusicDownloads folder and user-downloaded music
        """
        logger.info("Clearing internal cache from %s...", self._config.tdlib_files_dir)

        # 1. Clean TDLib files directory (cached audio parts, etc.)
        if self._config.tdlib_files_dir.exists():
            for item in self._config.tdlib_files_dir.glob("*"):
                try:
                    if item.is_file() or item.is_symlink():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                except Exception as exc:
                    logger.warning("Could not delete %s: %s", item, exc)

        # 2. Clean thumbnails directory (inside tdlib_dir)
        thumb_dir = self._config.tdlib_dir / "thumbnails"
        if thumb_dir.exists():
            for item in thumb_dir.glob("*"):
                try:
                    if item.is_file() or item.is_symlink():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                except Exception as exc:
                    logger.warning("Could not delete %s: %s", item, exc)

        logger.info("Internal cache cleared successfully. TMusicDownloads folder untouched.")