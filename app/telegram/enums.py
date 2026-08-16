from enum import StrEnum


class AuthState(StrEnum):
    """Normalized Telegram authorization states."""

    UNKNOWN = "unknown"
    WAIT_TDLIB_PARAMETERS = "wait_tdlib_parameters"
    WAIT_PHONE_NUMBER = "wait_phone_number"
    WAIT_CODE = "wait_code"
    WAIT_PASSWORD = "wait_password"  # 2FA Cloud Password
    READY = "ready"  # Successfully authenticated
    LOGGING_OUT = "logging_out"
    CLOSING = "closing"
    CLOSED = "closed"