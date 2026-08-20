from dataclasses import dataclass, field
import os
from pathlib import Path
import sys

from PySide6.QtCore import QStandardPaths

from app.platform.paths import get_default_downloads_dir

def _load_env(env_path: Path) -> dict[str, str]:
    env_vars: dict[str, str] = {}
    if not env_path.exists():
        return env_vars
    try:
        content = env_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            env_vars[key.strip()] = val.strip().strip("\"'")
    except Exception:
        pass
    return env_vars

def _get_root_and_bundle_dir() -> tuple[Path, Path]:
    if getattr(sys, "frozen", False):
        root = Path(sys.executable).resolve().parent
        bundle = Path(getattr(sys, "_MEIPASS", root))
        return root, bundle
    else:
        root = Path(__file__).resolve().parent.parent
        return root, root

def _get_api_id() -> int:
    val = os.getenv("TMUSIC_API_ID") or _ENV_VARS.get("TMUSIC_API_ID", "0")
    return int(val) if val.isdigit() else 0

def _get_api_hash() -> str:
    return os.getenv("TMUSIC_API_HASH") or _ENV_VARS.get("TMUSIC_API_HASH", "")

_ROOT_DIR, _BUNDLE_DIR = _get_root_and_bundle_dir()
_ENV_VARS = _load_env(_ROOT_DIR / ".env")

@dataclass(slots=True, frozen=True)
class AppConfig:
    app_name: str = "TMusic"
    app_version: str = "0.1.0"
    organization_name: str = "TMusicOrg"
    organization_domain: str = "tmusic.local"

    # Legacy paths for backward compatibility
    root_dir: Path = field(default=_ROOT_DIR)
    bundle_dir: Path = field(default=_BUNDLE_DIR)

    @property
    def app_full_name(self) -> str:
        """Full application name including version for session identification."""
        return f"{self.app_name} Desktop"

    @property
    def resources_dir(self) -> Path:
        return self.bundle_dir / "resources"

    @property
    def translations_dir(self) -> Path:
        return self.resources_dir / "translations"

    # Standard Qt paths (platform-independent)
    @property
    def app_data_dir(self) -> Path:
        path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        return Path(path) / "TMusicData"

    @property
    def cache_dir(self) -> Path:
        path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)
        return Path(path) / "TMusicData"

    # Root organization directories (for full wipe)
    @property
    def org_data_root(self) -> Path:
        """Root directory for application data (e.g. .../AppData/Roaming/TMusicOrg)"""
        return self.app_data_dir.parent.parent

    @property
    def org_cache_root(self) -> Path:
        """Root directory for cache data (e.g. .../AppData/Local/TMusicOrg)"""
        return self.cache_dir.parent.parent

    @property
    def tdlib_dir(self) -> Path:
        return self.app_data_dir / "tdlib"

    @property
    def tdlib_files_dir(self) -> Path:
        return self.cache_dir / "tdlib_files"

    @property
    def thumb_cache_dir(self) -> Path:
        return self.cache_dir / "thumbnails"

    @property
    def metadata_file(self) -> Path:
        return self.cache_dir / "cache_metadata.enc"

    @property
    def settings_file(self) -> Path:
        return self.app_data_dir / "settings.enc"
    
    # but we can add a helper to get the default explicitly if needed.
    @property
    def default_downloads_dir(self) -> Path:
        """Return the default downloads directory (may be different from settings)."""
        return self.downloads_dir

    downloads_dir: Path = field(default_factory=get_default_downloads_dir)

    api_id: int = field(default_factory=_get_api_id)
    api_hash: str = field(default_factory=_get_api_hash)

    def ensure_directories(self) -> None:
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.tdlib_dir.mkdir(parents=True, exist_ok=True)
        self.tdlib_files_dir.mkdir(parents=True, exist_ok=True)
        self.thumb_cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.downloads_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass