import base64
from dataclasses import asdict, dataclass, field
import logging
from pathlib import Path
from typing import Any

from app.core.security import CryptoManager
from app.models.chat import OwnedChat
from app.models.user import TelegramUser

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
    cached_user_profile: dict[str, Any] = field(default_factory=dict)


class SettingsService:
    """Manages secure encrypted user settings, cached chats, and avatar profile."""

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
                cached_user_profile=data.get("cached_user_profile", []),
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
            "cached_user_profile": self._preferences.cached_user_profile,
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

    def set_cached_user_profile(self, user: TelegramUser) -> None:
        """Cache user profile metadata and local avatar path."""
        minithumb_str = (
            base64.b64encode(user.minithumb_data).decode("ascii")
            if user.minithumb_data
            else None
        )
        self._preferences.cached_user_profile = {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "phone_number": user.phone_number,
            "photo_id": user.photo_id,
            "photo_file_id": user.photo_file_id,
            "photo_path": user.photo_path,
            "minithumb_data": minithumb_str,
        }
        self.save()

    def get_cached_user_profile(self) -> TelegramUser | None:
        """Retrieve user profile from secure local cache."""
        data = self._preferences.cached_user_profile
        if not data or "id" not in data:
            return None

        minithumb_raw = data.get("minithumb_data")
        minithumb_bytes = (
            base64.b64decode(minithumb_raw.encode("ascii"))
            if minithumb_raw
            else None
        )
        photo_path = data.get("photo_path")
        valid_path = photo_path if (photo_path and Path(photo_path).exists()) else None

        return TelegramUser(
            id=data["id"],
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            username=data.get("username", ""),
            phone_number=data.get("phone_number", ""),
            photo_id=data.get("photo_id", 0),
            photo_file_id=data.get("photo_file_id", 0),
            photo_path=valid_path,
            minithumb_data=minithumb_bytes,
        )

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