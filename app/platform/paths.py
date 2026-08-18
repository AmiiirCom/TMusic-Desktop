import logging
import os
from pathlib import Path
import re
import shutil
import tempfile
from PySide6.QtCore import QStandardPaths

logger = logging.getLogger("tmusic.platform.paths")


def get_default_downloads_dir() -> Path:
    """
    Securely resolve and create the native user Downloads/TMusicDownloads folder
    across Windows, macOS, and Linux with verified write permissions.
    """
    # 1. Query official OS Download location
    dl_location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
    if dl_location and Path(dl_location).exists():
        base_dir = Path(dl_location)
    else:
        # Fallback to standard user home Downloads
        base_dir = Path.home() / "Downloads"

    target_dir = base_dir / "TMusicDownloads"

    # 2. Secure Directory Creation
    try:
        target_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
    except OSError as exc:
        logger.warning("Could not create primary downloads directory %s: %s", target_dir, exc)
        # Safe fallback inside User Home directory
        target_dir = Path.home() / ".tmusic_downloads"
        target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    # 3. Verify write permissions with a temporary probe
    if not is_directory_writable(target_dir):
        logger.warning("Target downloads folder %s is read-only. Using fallback temp storage.", target_dir)
        fallback_dir = Path(tempfile.gettempdir()) / "TMusicDownloads"
        fallback_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        return fallback_dir

    return target_dir


def is_directory_writable(directory: Path) -> bool:
    """Verify that the target directory has actual write and modify permissions."""
    try:
        probe_file = directory / ".tmusic_write_test.tmp"
        probe_file.write_bytes(b"probe")
        probe_file.unlink(missing_ok=True)
        return True
    except (OSError, PermissionError):
        return False


def sanitize_filename(filename: str) -> str:
    """Sanitize filename removing forbidden characters across all OS filesystems."""
    clean = re.sub(r'[\\/*?:"<>|]', "_", filename).strip()
    clean = re.sub(r"\s+", " ", clean)
    return clean or "Track.mp3"


def has_sufficient_disk_space(target_dir: Path, required_bytes: int, margin_mb: int = 20) -> bool:
    """Verify disk free space before copying to prevent truncated writes."""
    try:
        if not target_dir.exists():
            target_dir.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(target_dir)
        return usage.free >= (required_bytes + margin_mb * 1024 * 1024)
    except Exception as exc:
        logger.warning("Could not check disk usage on %s: %s", target_dir, exc)
        return False