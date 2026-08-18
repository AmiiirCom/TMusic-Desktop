from dataclasses import dataclass, field
import os
from pathlib import Path
import sys

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


_ROOT_DIR, _BUNDLE_DIR = _get_root_and_bundle_dir()
_ENV_VARS = _load_env(_ROOT_DIR / ".env")


def _get_api_id() -> int:
    val = os.getenv("TMUSIC_API_ID") or _ENV_VARS.get("TMUSIC_API_ID", "0")
    return int(val) if val.isdigit() else 0


def _get_api_hash() -> str:
    return os.getenv("TMUSIC_API_HASH") or _ENV_VARS.get("TMUSIC_API_HASH", "")


@dataclass(slots=True, frozen=True)
class AppConfig:
    app_name: str = "TMusic"
    app_version: str = "1.0.0"
    organization_name: str = "TMusicOrg"
    organization_domain: str = "tmusic.local"

    # Base paths
    root_dir: Path = _ROOT_DIR
    bundle_dir: Path = _BUNDLE_DIR
    resources_dir: Path = _BUNDLE_DIR / "resources"
    translations_dir: Path = _BUNDLE_DIR / "resources" / "translations"
    data_dir: Path = _ROOT_DIR / "data"
    tdlib_dir: Path = _ROOT_DIR / "data" / "tdlib"

    # Internal cache for TDLib temp/subfolder files (kept private from user)
    tdlib_files_dir: Path = _ROOT_DIR / "data" / "cache"

    # Clean User-facing Downloads Folder (Contains ONLY completed audio tracks)
    downloads_dir: Path = field(default_factory=get_default_downloads_dir)

    # Loaded Telegram API credentials
    api_id: int = field(default_factory=_get_api_id)
    api_hash: str = field(default_factory=_get_api_hash)

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.tdlib_dir.mkdir(parents=True, exist_ok=True)
        self.tdlib_files_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.downloads_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass