import logging
import urllib.request
from urllib.parse import urlparse

logger = logging.getLogger("tmusic.settings.detector")


def detect_system_proxy() -> tuple[str, str, int, str, str] | None:
    """
    Detect OS-configured system proxy (Windows, macOS, Linux).
    Returns: (proxy_type, server, port, username, password) or None
    """
    try:
        proxies = urllib.request.getproxies()
        if not proxies:
            return None

        for proto in ("socks5", "socks", "https", "http"):
            if proto in proxies:
                raw_url = proxies[proto]
                if not raw_url:
                    continue
                if not raw_url.startswith(("http://", "https://", "socks://", "socks5://")):
                    raw_url = f"{proto}://{raw_url}"

                parsed = urlparse(raw_url)
                p_type = "SOCKS5" if "sock" in proto else "HTTP"
                host = parsed.hostname or "127.0.0.1"
                port = parsed.port or (10808 if p_type == "SOCKS5" else 8080)
                user = parsed.username or ""
                pwd = parsed.password or ""
                return (p_type, host, port, user, pwd)
    except Exception as exc:
        logger.debug("Failed to detect system proxy: %s", exc)
    return None