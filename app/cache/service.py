import logging
from pathlib import Path
import shutil

from app.config import AppConfig

logger = logging.getLogger("tmusic.cache.service")


class CacheService:
    """Manages downloaded media files and downloads directory usage."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    @property
    def downloads_path(self) -> Path:
        return self._config.downloads_dir

    def get_cache_size_bytes(self) -> int:
        """Calculate total disk usage of downloaded media in bytes."""
        total = 0
        if self._config.downloads_dir.exists():
            for p in self._config.downloads_dir.rglob("*"):
                if p.is_file():
                    total += p.stat().st_size
        return total

    def get_formatted_cache_size(self) -> str:
        size = self.get_cache_size_bytes()
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    def clear_cache(self) -> None:
        """Clear all downloaded media files safely."""
        logger.info("Clearing downloaded media files from %s...", self._config.downloads_dir)
        if self._config.downloads_dir.exists():
            for item in self._config.downloads_dir.iterdir():
                try:
                    if item.is_file() or item.is_symlink():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                except Exception as exc:
                    logger.warning("Could not delete file %s: %s", item, exc)
        logger.info("Downloads directory cleared successfully.")