from PySide6.QtCore import QObject, Signal


def format_bytes(byte_count: int) -> str:
    """Format byte count into human readable B, KB, MB, or GB."""
    if byte_count < 1024:
        return f"{byte_count} B"
    elif byte_count < 1024 * 1024:
        return f"{byte_count / 1024:.1f} KB"
    elif byte_count < 1024 * 1024 * 1024:
        return f"{byte_count / (1024 * 1024):.1f} MB"
    return f"{byte_count / (1024 * 1024 * 1024):.2f} GB"


def format_speed(bytes_per_sec: int) -> str:
    """Format speed in bytes per second into readable rate."""
    if bytes_per_sec < 1024:
        return f"{bytes_per_sec} B/s"
    elif bytes_per_sec < 1024 * 1024:
        return f"{bytes_per_sec / 1024:.0f} KB/s"
    return f"{bytes_per_sec / (1024 * 1024):.1f} MB/s"


class NetworkMeter(QObject):
    """
    Precision network traffic meter tracking total session usage
    and live real-time bandwidth speeds from TDLib network stats from the moment of launch.
    """

    stats_updated = Signal(str, str)  # (live_speed_str, session_usage_str)
    full_stats_updated = Signal(str, str, str)  # (speed_str, rx_str, tx_str)

    def __init__(self) -> None:
        super().__init__()
        self._is_initialized: bool = False
        self._initial_rx: int = 0
        self._initial_tx: int = 0
        self._last_rx: int = 0
        self._last_tx: int = 0
        self._session_rx: int = 0
        self._session_tx: int = 0

    def update_network_stats(self, total_rx_bytes: int, total_tx_bytes: int) -> None:
        """Process absolute network counters received from TDLib."""
        # Record baseline on the very first reading at startup
        if not self._is_initialized:
            self._is_initialized = True
            self._initial_rx = total_rx_bytes
            self._initial_tx = total_tx_bytes
            self._last_rx = total_rx_bytes
            self._last_tx = total_tx_bytes
            self.stats_updated.emit("0 KB/s", "0 B")
            self.full_stats_updated.emit("0 KB/s", "0 B", "0 B")
            return

        # Calculate session delta (total data consumed since application launched)
        self._session_rx = max(0, total_rx_bytes - self._initial_rx)
        self._session_tx = max(0, total_tx_bytes - self._initial_tx)

        # Calculate live speed over the last interval (1s)
        delta_rx = max(0, total_rx_bytes - self._last_rx)
        self._last_rx = total_rx_bytes
        self._last_tx = total_tx_bytes

        speed_str = format_speed(delta_rx)
        session_rx_str = format_bytes(self._session_rx)
        session_tx_str = format_bytes(self._session_tx)

        self.stats_updated.emit(speed_str, session_rx_str)
        self.full_stats_updated.emit(speed_str, session_rx_str, session_tx_str)