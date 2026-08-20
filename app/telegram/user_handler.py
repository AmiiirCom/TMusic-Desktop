import base64
import logging
from pathlib import Path
from typing import Any, Callable

from app.config import AppConfig
from app.core.image_compressor import compress_image, get_compressed_image_path
from app.models.user import TelegramUser
from app.settings.service import SettingsService
from app.telegram.adapter import TDLibAdapter

logger = logging.getLogger("tmusic.telegram.user")


class UserHandler:
    """Manages authenticated user profile retrieval, caching, and avatar image processing."""

    def __init__(
        self,
        config: AppConfig,
        adapter: TDLibAdapter,
        settings_service: SettingsService | None,
        on_user_loaded: Callable[[TelegramUser], None],
    ) -> None:
        self._config = config
        self._adapter = adapter
        self._settings = settings_service
        self._on_user_loaded = on_user_loaded

        self._my_user_id: int = 0
        self._current_user: TelegramUser | None = None
        self._avatar_file_id: int = 0

    @property
    def current_user(self) -> TelegramUser | None:
        return self._current_user

    @property
    def my_user_id(self) -> int:
        return self._my_user_id

    @property
    def avatar_file_id(self) -> int:
        return self._avatar_file_id

    def set_settings_service(self, settings_service: SettingsService) -> None:
        self._settings = settings_service

    def load_cached_user(self) -> None:
        if not self._settings:
            return
        cached_user = self._settings.get_cached_user_profile()
        if cached_user:
            self._current_user = cached_user
            self._my_user_id = cached_user.id
            self._on_user_loaded(cached_user)

    def extract_user(self, user_obj: dict[str, Any], is_self: bool = False) -> TelegramUser | None:
        user_id = user_obj.get("id", 0)
        if not user_id or (not is_self and self._my_user_id != 0 and user_id != self._my_user_id):
            return None

        self._my_user_id = user_id
        usernames = user_obj.get("usernames", {})
        active = usernames.get("active_usernames", [])
        username = active[0] if active else user_obj.get("username", "")

        photo = user_obj.get("profile_photo", {})
        photo_id = photo.get("id", 0)
        target_file = (photo.get("big") or photo.get("small") or {}) if photo else {}
        photo_file_id = target_file.get("id", 0)
        photo_local = target_file.get("local", {})
        photo_path = photo_local.get("path") if photo_local.get("is_downloading_completed") else None

        minithumb = photo.get("minithumbnail") if photo else None
        minithumb_data = (
            base64.b64decode(minithumb["data"])
            if minithumb and "data" in minithumb
            else None
        )

        cached = self._settings.get_cached_user_profile() if self._settings else None
        if cached and str(cached.photo_id) == str(photo_id) and cached.photo_path and Path(cached.photo_path).exists():
            photo_path = cached.photo_path
        elif photo_file_id > 0 and not photo_path and self._adapter.is_loaded:
            self._avatar_file_id = photo_file_id
            self._adapter.send({
                "@type": "downloadFile",
                "file_id": photo_file_id,
                "priority": 16,
                "offset": 0,
                "limit": 0,
                "synchronous": False,
            })

        user = TelegramUser(
            id=user_id,
            first_name=user_obj.get("first_name", ""),
            last_name=user_obj.get("last_name", ""),
            username=username,
            phone_number=user_obj.get("phone_number", ""),
            photo_id=photo_id,
            photo_file_id=photo_file_id,
            photo_path=photo_path,
            minithumb_data=minithumb_data,
        )
        self._current_user = user
        if self._settings:
            self._settings.set_cached_user_profile(user)
        self._on_user_loaded(user)
        return user

    def handle_avatar_file(self, orig_path: Path) -> TelegramUser | None:
        if not orig_path.exists() or not self._current_user:
            return None

        compressed = get_compressed_image_path(self._config.thumb_cache_dir, "avatar", str(self._current_user.id))
        result = compress_image(orig_path, compressed)
        if result:
            self._current_user = TelegramUser(
                id=self._current_user.id,
                first_name=self._current_user.first_name,
                last_name=self._current_user.last_name,
                username=self._current_user.username,
                phone_number=self._current_user.phone_number,
                photo_id=self._current_user.photo_id,
                photo_file_id=self._avatar_file_id,
                photo_path=str(result),
                minithumb_data=self._current_user.minithumb_data,
            )
            if self._settings:
                self._settings.set_cached_user_profile(self._current_user)
            self._on_user_loaded(self._current_user)
            orig_path.unlink(missing_ok=True)
            return self._current_user

        return None