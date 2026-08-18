from pathlib import Path
from PySide6.QtCore import QStandardPaths


def get_default_downloads_dir() -> Path:
    """
    Resolve the native OS Downloads folder cross-platform
    and create the TMusicDownloads directory.
    - Windows: C:\\Users\\<User>\\Downloads\\TMusicDownloads
    - macOS:   /Users/<User>/Downloads/TMusicDownloads
    - Linux:   /home/<User>/Downloads/TMusicDownloads
    """
    dl_location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
    base_dir = Path(dl_location) if dl_location else Path.home() / "Downloads"

    target_dir = base_dir / "TMusicDownloads"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir