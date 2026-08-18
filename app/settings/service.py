from dataclasses import asdict, dataclass, field
import logging
from pathlib import Path
from typing import Any

from app.core.security import CryptoManager
from app.models.chat import OwnedChat

logger = logging.getLogger("tmusic.settings.service")


@dataclass(slots=True)
class ProxySettings:
    enabled: bool = False
    proxy_type: str = "SOCKS5"
    server: str = "127.0.0.1"
    port: int = 10808
    username: str = ""
    password: str = ""


@dataclass(slots=True)
class UserPreferences:
    volume: int = 80
    is_muted: bool = False
    playback_rate: float = 1.0
    minimize_to_tray: bool = True
    last_chat_id: int = 0
    proxy: ProxySettings = field(default_factory=ProxySettings)
    cached_music_chats: list[dict[str, Any]] = field(default_factory=list)


class SettingsService:
    """Manages secure encrypted user settings and cached music channels."""

    def __init__(self, data_dir: Path, crypto: CryptoManager) -> None:
        self._data_dir = data_dir
        self._crypto = crypto
        self._settings_file = data_dir / "settings.enc"
        self._preferences = UserPreferences()
        self.load()

    @property
    def preferences(self) -> UserPreferences:
        return self._preferences

    def load(self) -> None:
        """Load and decrypt settings from disk."""
        data = self._crypto.load_encrypted_json(self._settings_file)
        if not data:
            return

        try:
            proxy_data = data.get("proxy", {})
            proxy = ProxySettings(
                enabled=proxy_data.get("enabled", False),
                proxy_type=proxy_data.get("proxy_type", "SOCKS5"),
                server=proxy_data.get("server", "127.0.0.1"),
                port=proxy_data.get("port", 10808),
                username=proxy_data.get("username", ""),
                password=proxy_data.get("password", ""),
            )

            self._preferences = UserPreferences(
                volume=data.get("volume", 80),
                is_muted=data.get("is_muted", False),
                playback_rate=float(data.get("playback_rate", 1.0)),
                minimize_to_tray=data.get("minimize_to_tray", True),
                last_chat_id=data.get("last_chat_id", 0),
                proxy=proxy,
                cached_music_chats=data.get("cached_music_chats", []),
            )
            logger.info("Loaded secure encrypted preferences successfully.")
        except Exception as exc:
            logger.warning("Error parsing settings data: %s", exc)

    def save(self) -> None:
        """Encrypt and persist current settings to disk."""
        payload: dict[str, Any] = {
            "volume": self._preferences.volume,
            "is_muted": self._preferences.is_muted,
            "playback_rate": self._preferences.playback_rate,
            "minimize_to_tray": self._preferences.minimize_to_tray,
            "last_chat_id": self._preferences.last_chat_id,
            "proxy": asdict(self._preferences.proxy),
            "cached_music_chats": self._preferences.cached_music_chats,
        }
        self._crypto.save_encrypted_json(self._settings_file, payload)

    def set_cached_music_chats(self, chats: list[OwnedChat]) -> None:
        self._preferences.cached_music_chats = [
            {
                "id": c.id,
                "title": c.title,
                "is_channel": c.is_channel,
                "supergroup_id": c.supergroup_id,
                "unread_count": c.unread_count,
            }
            for c in chats
        ]
        self.save()

    def get_cached_music_chats(self) -> list[OwnedChat]:
        return [
            OwnedChat(
                id=c["id"],
                title=c["title"],
                is_channel=c.get("is_channel", True),
                supergroup_id=c.get("supergroup_id", 0),
                unread_count=c.get("unread_count", 0),
            )
            for c in self._preferences.cached_music_chats
            if "id" in c and "title" in c
        ]

    def set_proxy(self, proxy_type: str, server: str, port: int, enabled: bool = True) -> None:
        self._preferences.proxy.enabled = enabled
        self._preferences.proxy.proxy_type = proxy_type
        self._preferences.proxy.server = server
        self._preferences.proxy.port = port
        self.save()

    def set_volume(self, volume: int) -> None:
        self._preferences.volume = volume
        self.save()

    def set_playback_rate(self, rate: float) -> None:
        self._preferences.playback_rate = rate
        self.save()

    def set_last_chat(self, chat_id: int) -> None:
        self._preferences.last_chat_id = chat_id
        self.save()