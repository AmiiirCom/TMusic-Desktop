import logging
from pathlib import Path
import shutil

from app.config import AppConfig

logger = logging.getLogger("tmusic.cache.service")


class CacheService:
    """Manages downloaded media files inside clean TMusicDownloads folder and internal cache."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    @property
    def downloads_path(self) -> Path:
        return self._config.downloads_dir

    def get_cache_size_bytes(self) -> int:
        """Calculate total disk usage of completed music files in TMusicDownloads."""
        total = 0
        if self._config.downloads_dir.exists():
            for p in self._config.downloads_dir.glob("*"):
                if p.is_file():
                    total += p.stat().st_size
        return total

    def get_formatted_cache_size(self) -> str:
        size = self.get_cache_size_bytes()
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    def clear_cache(self) -> None:
        """Clear all downloaded music files in TMusicDownloads and internal temp cache."""
        logger.info("Clearing clean music files from %s...", self._config.downloads_dir)
        if self._config.downloads_dir.exists():
            for item in self._config.downloads_dir.glob("*"):
                try:
                    if item.is_file() or item.is_symlink():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                except Exception as exc:
                    logger.warning("Could not delete %s: %s", item, exc)

        # Also clean internal temp cache
        if self._config.tdlib_files_dir.exists():
            for item in self._config.tdlib_files_dir.glob("*"):
                try:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                except Exception:
                    pass
        logger.info("Downloads and internal temp cache cleared successfully.")