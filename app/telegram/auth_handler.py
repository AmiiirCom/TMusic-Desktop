import logging
from typing import Any, Callable

from app.config import AppConfig
from app.telegram.adapter import TDLibAdapter
from app.telegram.enums import AuthState

logger = logging.getLogger("tmusic.telegram.auth")


class AuthHandler:
    """Manages TDLib authorization state machine and credential submissions."""

    def __init__(
        self,
        config: AppConfig,
        adapter: TDLibAdapter,
        on_auth_state_changed: Callable[[AuthState], None],
        on_auth_ready: Callable[[], None],
    ) -> None:
        self._config = config
        self._adapter = adapter
        self._on_auth_state_changed = on_auth_state_changed
        self._on_auth_ready = on_auth_ready
        self._auth_state = AuthState.UNKNOWN

    @property
    def current_state(self) -> AuthState:
        return self._auth_state

    def process_update(self, auth_state_obj: dict[str, Any]) -> None:
        """Process updateAuthorizationState from TDLib."""
        state_type = auth_state_obj.get("@type", "")
        logger.info("TDLib Auth State: %s", state_type)

        match state_type:
            case "authorizationStateWaitTdlibParameters":
                self._auth_state = AuthState.WAIT_TDLIB_PARAMETERS
                self._send_tdlib_parameters()

            case "authorizationStateWaitPhoneNumber":
                self._auth_state = AuthState.WAIT_PHONE_NUMBER

            case "authorizationStateWaitCode":
                self._auth_state = AuthState.WAIT_CODE

            case "authorizationStateWaitPassword":
                self._auth_state = AuthState.WAIT_PASSWORD

            case "authorizationStateReady":
                self._auth_state = AuthState.READY
                logger.info("Authorization READY!")
                self._on_auth_ready()

            case "authorizationStateLoggingOut":
                self._auth_state = AuthState.LOGGING_OUT

            case "authorizationStateClosed":
                self._auth_state = AuthState.CLOSED

            case _:
                self._auth_state = AuthState.UNKNOWN

        self._on_auth_state_changed(self._auth_state)

    def _send_tdlib_parameters(self) -> None:
        self._config.ensure_directories()
        params = {
            "@type": "setTdlibParameters",
            "use_test_dc": False,
            "database_directory": str(self._config.tdlib_dir),
            "files_directory": str(self._config.cache_dir),
            "use_file_database": True,
            "use_chat_info_database": True,
            "use_message_database": True,
            "use_secret_chats": False,
            "api_id": self._config.api_id,
            "api_hash": self._config.api_hash,
            "system_language_code": "fa",
            "device_model": "Desktop",
            "system_version": "Windows",
            "application_version": self._config.app_version,
            "enable_storage_optimizer": True,
        }
        self._adapter.send(params)

    def send_phone_number(self, phone_number: str) -> None:
        if self._auth_state != AuthState.WAIT_PHONE_NUMBER:
            logger.warning("Ignoring phone submission: Auth state is %s", self._auth_state)
            return

        self._adapter.send({
            "@type": "setAuthenticationPhoneNumber",
            "phone_number": phone_number.strip(),
            "settings": {"@type": "phoneNumberAuthenticationSettings"},
        })

    def send_code(self, code: str) -> None:
        if self._auth_state != AuthState.WAIT_CODE:
            logger.warning("Ignoring code submission: Auth state is %s", self._auth_state)
            return

        self._adapter.send({"@type": "checkAuthenticationCode", "code": code.strip()})

    def send_password(self, password: str) -> None:
        if self._auth_state != AuthState.WAIT_PASSWORD:
            logger.warning("Ignoring password submission: Auth state is %s", self._auth_state)
            return

        self._adapter.send({"@type": "checkAuthenticationPassword", "password": password})