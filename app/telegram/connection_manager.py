import logging
from typing import Callable
from PySide6.QtCore import QObject, QTimer, Signal

from app.settings.detector import detect_system_proxy
from app.settings.models import ProxySettings
from app.telegram.adapter import TDLibAdapter

logger = logging.getLogger("tmusic.telegram.connection")

CONNECTED_HEALTH_CHECK_INTERVAL_MS = 90_000
INITIAL_RETRY_INTERVAL_SEC = 15
RETRY_INTERVAL_STEP_SEC = 15
MAX_RETRY_INTERVAL_SEC = 120


class ConnectionManager(QObject):
    """Manages connection health checks, incremental reconnect backoff, and proxy dispatching."""

    retry_interval_changed = Signal(int)

    def __init__(self, adapter: TDLibAdapter, get_proxy_settings: Callable[[], ProxySettings | None]) -> None:
        super().__init__()
        self._adapter = adapter
        self._get_proxy_settings = get_proxy_settings

        self._health_timer = QTimer(self)
        self._health_timer.setInterval(CONNECTED_HEALTH_CHECK_INTERVAL_MS)
        self._health_timer.timeout.connect(self._on_health_ping)

        self._current_retry_interval = INITIAL_RETRY_INTERVAL_SEC
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(self._on_reconnect_retry)

    def handle_connection_state(self, state: str) -> None:
        if state == "connectionStateReady":
            self._current_retry_interval = INITIAL_RETRY_INTERVAL_SEC
            self._reconnect_timer.stop()
            self.retry_interval_changed.emit(0)
            if not self._health_timer.isActive():
                self._health_timer.start()
        else:
            self._health_timer.stop()
            if not self._reconnect_timer.isActive():
                self._reconnect_timer.start(self._current_retry_interval * 1000)
                self.retry_interval_changed.emit(self._current_retry_interval)

    def _on_health_ping(self) -> None:
        if self._adapter.is_loaded:
            self._adapter.send({"@type": "getOption", "name": "version", "@extra": "health_ping"})

    def _on_reconnect_retry(self) -> None:
        if not self._adapter.is_loaded:
            return

        proxy = self._get_proxy_settings()
        if proxy:
            self.apply_proxy_settings(proxy)

        next_interval = min(MAX_RETRY_INTERVAL_SEC, self._current_retry_interval + RETRY_INTERVAL_STEP_SEC)
        self._current_retry_interval = next_interval
        self.retry_interval_changed.emit(self._current_retry_interval)
        self._reconnect_timer.start(self._current_retry_interval * 1000)

    def apply_proxy_settings(self, proxy: ProxySettings) -> None:
        if proxy.mode == "DIRECT" or not proxy.enabled:
            self.disable_proxy()
        elif proxy.mode == "SYSTEM":
            sys_proxy = detect_system_proxy()
            if sys_proxy:
                ptype, server, port, user, pwd = sys_proxy
                if ptype == "SOCKS5":
                    self.set_socks5_proxy(server, port, user, pwd)
                else:
                    self.set_http_proxy(server, port, user, pwd)
            else:
                self.disable_proxy()
        elif proxy.mode == "CUSTOM":
            if proxy.proxy_type == "SOCKS5":
                self.set_socks5_proxy(proxy.server, proxy.port, proxy.username, proxy.password)
            else:
                self.set_http_proxy(proxy.server, proxy.port, proxy.username, proxy.password)

    def disable_proxy(self) -> None:
        if self._adapter.is_loaded:
            self._adapter.send({"@type": "disableProxy"})

    def set_socks5_proxy(self, server: str, port: int, username: str = "", password: str = "") -> None:
        self._adapter.send({
            "@type": "addProxy",
            "proxy": {
                "@type": "proxy",
                "server": server.strip(),
                "port": int(port),
                "last_used_date": 0,
                "type": {"@type": "proxyTypeSocks5", "username": username, "password": password},
            },
            "enable": True,
        })

    def set_http_proxy(self, server: str, port: int, username: str = "", password: str = "") -> None:
        self._adapter.send({
            "@type": "addProxy",
            "proxy": {
                "@type": "proxy",
                "server": server.strip(),
                "port": int(port),
                "last_used_date": 0,
                "type": {"@type": "proxyTypeHttp", "username": username, "password": password},
            },
            "enable": True,
        })

    def stop(self) -> None:
        self._health_timer.stop()
        self._reconnect_timer.stop()