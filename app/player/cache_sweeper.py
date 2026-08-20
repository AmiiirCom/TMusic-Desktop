import logging
from pathlib import Path
import shutil
import threading
from typing import Callable

from app.config import AppConfig
from app.core.metadata import parse_id3v2_tags_from_bytes
from app.platform.paths import has_sufficient_disk_space, sanitize_filename

logger = logging.getLogger("tmusic.player.sweeper")

AUDIO_EXTENSIONS = (".mp3", ".flac", ".m4a", ".wav", ".aac", ".ogg", ".opus")


class CacheSweeper:
    """Background worker for exporting and cleaning TDLib cache files."""

    def __init__(self, config: AppConfig, is_save_to_downloads_enabled: Callable[[], bool]) -> None:
        self._config = config
        self._is_save_enabled = is_save_to_downloads_enabled
        self._sweep_lock = threading.Lock()

    def start_sweep(self, async_mode: bool = True) -> None:
        if async_mode:
            threading.Thread(target=self._run_sweep, name="CacheSweeperThread", daemon=True).start()
        else:
            self._run_sweep()

    def purge_cache_files(self) -> None:
        cache_dir = self._config.tdlib_files_dir
        if not cache_dir.exists():
            return

        for file_path in cache_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in AUDIO_EXTENSIONS:
                try:
                    file_path.unlink(missing_ok=True)
                except Exception:
                    pass

    def _run_sweep(self) -> None:
        if not self._sweep_lock.acquire(blocking=False):
            return

        try:
            if not self._is_save_enabled():
                self.purge_cache_files()
                return

            cache_dir = self._config.tdlib_files_dir
            if not cache_dir.exists():
                return

            for file_path in cache_dir.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in AUDIO_EXTENSIONS:
                    if file_path.stat().st_size == 0 or file_path.name.endswith(".temp"):
                        continue

                    clean_name = self.resolve_clean_filename(file_path)
                    dest_file = self._config.downloads_dir / clean_name

                    try:
                        self._config.downloads_dir.mkdir(parents=True, exist_ok=True)
                        src_size = file_path.stat().st_size

                        if has_sufficient_disk_space(self._config.downloads_dir, src_size):
                            if not dest_file.exists() or dest_file.stat().st_size != src_size:
                                shutil.copy2(file_path, dest_file)

                            if dest_file.exists() and dest_file.stat().st_size == src_size:
                                file_path.unlink(missing_ok=True)
                    except Exception as exc:
                        logger.debug("Error exporting cache file %s: %s", file_path, exc)
        finally:
            self._sweep_lock.release()

    @staticmethod
    def resolve_clean_filename(file_path: Path) -> str:
        ext = file_path.suffix or ".mp3"
        try:
            with open(file_path, "rb") as f:
                meta = parse_id3v2_tags_from_bytes(f.read(512 * 1024))
                if meta.title and meta.artist:
                    return sanitize_filename(f"{meta.artist} - {meta.title}{ext}")
                elif meta.title:
                    return sanitize_filename(f"{meta.title}{ext}")
        except Exception:
            pass
        return sanitize_filename(file_path.name)