import base64
from dataclasses import asdict
import logging
from pathlib import Path
from typing import Any

from app.config import AppConfig
from app.core.security import CryptoManager
from app.models.chat import OwnedChat
from app.models.user import TelegramUser
from app.settings.detector import detect_system_proxy
from app.settings.models import ProxySettings, UserPreferences

logger = logging.getLogger("tmusic.settings.service")

__all__ = [
    "detect_system_proxy",
    "ProxySettings",
    "UserPreferences",
    "SettingsService",
]


class SettingsService:
    """Manages encrypted user settings, cached chats, and persistent track registry."""

    def __init__(self, config: AppConfig, crypto: CryptoManager) -> None:
        self._config = config
        self._crypto = crypto
        self._settings_file = config.settings_file
        self._preferences = UserPreferences()
        self.load()

    @property
    def preferences(self) -> UserPreferences:
        return self._preferences

    def load(self) -> None:
        data = self._crypto.load_encrypted_json(self._settings_file)
        if not data:
            return

        try:
            proxy_data = data.get("proxy", {})
            mode = proxy_data.get("mode") or ("CUSTOM" if proxy_data.get("enabled", False) else "DIRECT")

            proxy = ProxySettings(
                mode=mode,
                enabled=(mode != "DIRECT"),
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
                save_to_downloads=data.get("save_to_downloads", True),
                last_chat_id=data.get("last_chat_id", 0),
                proxy=proxy,
                cached_music_chats=data.get("cached_music_chats", []),
                cached_user_profile=data.get("cached_user_profile", {}),
                downloaded_tracks_map=data.get("downloaded_tracks_map", {}),
            )
            logger.info("Loaded secure encrypted preferences successfully.")
        except Exception as exc:
            logger.warning("Error parsing settings data: %s", exc)

    def save(self) -> None:
        payload: dict[str, Any] = {
            "volume": self._preferences.volume,
            "is_muted": self._preferences.is_muted,
            "playback_rate": self._preferences.playback_rate,
            "minimize_to_tray": self._preferences.minimize_to_tray,
            "save_to_downloads": self._preferences.save_to_downloads,
            "last_chat_id": self._preferences.last_chat_id,
            "proxy": asdict(self._preferences.proxy),
            "cached_music_chats": self._preferences.cached_music_chats,
            "cached_user_profile": self._preferences.cached_user_profile,
            "downloaded_tracks_map": self._preferences.downloaded_tracks_map,
        }
        self._crypto.save_encrypted_json(self._settings_file, payload)

    def register_downloaded_track(self, track_id: str, file_id: int, local_path: str) -> None:
        self._preferences.downloaded_tracks_map[track_id] = local_path
        self._preferences.downloaded_tracks_map[str(file_id)] = local_path
        self.save()

    def get_downloaded_track_path(self, track_id: str, file_id: int) -> str | None:
        path_str = (
            self._preferences.downloaded_tracks_map.get(track_id)
            or self._preferences.downloaded_tracks_map.get(str(file_id))
        )
        if path_str and Path(path_str).exists() and Path(path_str).stat().st_size > 0:
            return path_str
        return None

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

    def set_proxy_settings(self, proxy: ProxySettings) -> None:
        self._preferences.proxy = proxy
        self.save()

    def set_volume(self, volume: int) -> None:
        self._preferences.volume = volume
        self.save()

    def set_playback_rate(self, rate: float) -> None:
        self._preferences.playback_rate = rate
        self.save()

    def set_save_to_downloads(self, enabled: bool) -> None:
        self._preferences.save_to_downloads = enabled
        self.save()

    def set_last_chat(self, chat_id: int) -> None:
        self._preferences.last_chat_id = chat_id
        self.save()