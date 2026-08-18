import ctypes
import json
import logging
from pathlib import Path
import platform
import sys
import threading
from typing import Any
import uuid

logger = logging.getLogger("tmusic.telegram.adapter")


class TDLibError(Exception):
    """Base exception for TDLib errors."""


class TDLibAdapter:
    """Low-level FFI binding for TDLib JSON client with request-response dispatching."""

    def __init__(self, library_path: Path | str | None = None) -> None:
        self._library_path = self._resolve_library_path(library_path)
        self._tdlib: ctypes.CDLL | None = None
        self._client: ctypes.c_void_p | None = None

        # Request-response dispatcher map: extra_id -> (threading.Event, response_holder)
        self._pending_requests: dict[str, tuple[threading.Event, list[dict[str, Any]]]] = {}
        self._requests_lock = threading.Lock()

        self._load_library()

    def _resolve_library_path(self, custom_path: Path | str | None) -> Path:
        if custom_path:
            return Path(custom_path)

        system = platform.system()
        filename = (
            "tdjson.dll"
            if system == "Windows"
            else ("libtdjson.dylib" if system == "Darwin" else "libtdjson.so")
        )

        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).resolve().parent
            bundle_dir = Path(getattr(sys, "_MEIPASS", exe_dir))
            candidates = [
                exe_dir / "native" / filename,
                exe_dir / filename,
                bundle_dir / "native" / filename,
                bundle_dir / filename,
            ]
        else:
            root_dir = Path(__file__).resolve().parent.parent.parent
            candidates = [
                root_dir / "native" / filename,
                root_dir / filename,
            ]

        for cand in candidates:
            if cand.exists():
                return cand

        return candidates[0]

    def _load_library(self) -> None:
        if not self._library_path.exists():
            logger.warning("TDLib binary not found at %s", self._library_path)
            return

        try:
            self._tdlib = ctypes.CDLL(str(self._library_path))

            self._tdlib.td_json_client_create.restype = ctypes.c_void_p
            self._tdlib.td_json_client_create.argtypes = []

            self._tdlib.td_json_client_send.restype = None
            self._tdlib.td_json_client_send.argtypes = [ctypes.c_void_p, ctypes.c_char_p]

            self._tdlib.td_json_client_receive.restype = ctypes.c_char_p
            self._tdlib.td_json_client_receive.argtypes = [ctypes.c_void_p, ctypes.c_double]

            self._tdlib.td_json_client_execute.restype = ctypes.c_char_p
            self._tdlib.td_json_client_execute.argtypes = [ctypes.c_void_p, ctypes.c_char_p]

            self._tdlib.td_json_client_destroy.restype = None
            self._tdlib.td_json_client_destroy.argtypes = [ctypes.c_void_p]

            self._client = self._tdlib.td_json_client_create()
            self.execute({"@type": "setLogVerbosityLevel", "new_verbosity_level": 1})
            logger.info("TDLib library loaded successfully from %s", self._library_path)

        except Exception as exc:
            logger.exception("Failed to load TDLib library: %s", exc)
            raise TDLibError(f"Could not load TDLib binary: {exc}") from exc

    @property
    def is_loaded(self) -> bool:
        return self._client is not None

    def send(self, query: dict[str, Any]) -> None:
        if not self._client or not self._tdlib:
            raise TDLibError("TDLib client is not initialized")

        query_bytes = json.dumps(query).encode("utf-8")
        self._tdlib.td_json_client_send(self._client, query_bytes)

    def request_sync(self, query: dict[str, Any], timeout: float = 3.0) -> dict[str, Any] | None:
        """Send query with @extra and wait synchronously for response in a thread-safe way."""
        extra_id = f"req_{uuid.uuid4().hex}"
        query["@extra"] = extra_id

        event = threading.Event()
        holder: list[dict[str, Any]] = []

        with self._requests_lock:
            self._pending_requests[extra_id] = (event, holder)

        try:
            self.send(query)
            if event.wait(timeout=timeout) and holder:
                return holder[0]
            return None
        finally:
            with self._requests_lock:
                self._pending_requests.pop(extra_id, None)

    def receive(self, timeout: float = 1.0) -> dict[str, Any] | None:
        if not self._client or not self._tdlib:
            return None

        result_ptr = self._tdlib.td_json_client_receive(self._client, ctypes.c_double(timeout))
        if not result_ptr:
            return None

        try:
            update = json.loads(result_ptr.decode("utf-8"))

            # Check if this update matches a pending synchronous request
            extra = update.get("@extra")
            if extra and isinstance(extra, str):
                with self._requests_lock:
                    if extra in self._pending_requests:
                        event, holder = self._pending_requests[extra]
                        holder.append(update)
                        event.set()

            return update
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.error("Failed to decode TDLib response: %s", exc)
            return None

    def execute(self, query: dict[str, Any]) -> dict[str, Any] | None:
        if not self._tdlib:
            return None

        query_bytes = json.dumps(query).encode("utf-8")
        result_ptr = self._tdlib.td_json_client_execute(self._client, query_bytes)
        if not result_ptr:
            return None

        try:
            return json.loads(result_ptr.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def close(self) -> None:
        if self._client and self._tdlib:
            logger.info("Destroying TDLib client instance")
            self._tdlib.td_json_client_destroy(self._client)
            self._client = None