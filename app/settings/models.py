from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ProxySettings:
    """Data model representing Telegram proxy settings."""

    mode: str = "DIRECT"  # "DIRECT", "SYSTEM", "CUSTOM"
    enabled: bool = False
    proxy_type: str = "SOCKS5"
    server: str = "127.0.0.1"
    port: int = 10808
    username: str = ""
    password: str = ""


@dataclass(slots=True)
class UserPreferences:
    """Data model representing persistent application preferences."""

    volume: int = 80
    is_muted: bool = False
    playback_rate: float = 1.0
    minimize_to_tray: bool = True
    save_to_downloads: bool = True
    last_chat_id: int = 0
    proxy: ProxySettings = field(default_factory=ProxySettings)
    cached_music_chats: list[dict[str, Any]] = field(default_factory=list)
    cached_user_profile: dict[str, Any] = field(default_factory=dict)
    downloaded_tracks_map: dict[str, str] = field(default_factory=dict)