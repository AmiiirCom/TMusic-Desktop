from PySide6.QtCore import QObject, QTimer, Signal


class NetworkMeter(QObject):
    """Tracks real-time network traffic and current download speeds."""

    stats_updated = Signal(str, str)  # (current_speed_str, total_usage_str)

    def __init__(self) -> None:
        super().__init__()
        self._total_bytes = 0
        self._last_tick_bytes = 0

        # Update speed every 1 second
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

    def record_download(self, byte_count: int) -> None:
        """Record newly downloaded bytes from network."""
        if byte_count > 0:
            self._total_bytes += byte_count

    def _on_tick(self) -> None:
        delta_bytes = self._total_bytes - self._last_tick_bytes
        self._last_tick_bytes = self._total_bytes

        # Calculate current speed
        if delta_bytes >= 1024 * 1024:
            speed_str = f"{delta_bytes / (1024 * 1024):.1f} MB/s"
        elif delta_bytes >= 1024:
            speed_str = f"{delta_bytes / 1024:.0f} KB/s"
        else:
            speed_str = "0 KB/s"

        # Calculate total session usage
        if self._total_bytes >= 1024 * 1024:
            total_str = f"{self._total_bytes / (1024 * 1024):.1f} MB"
        else:
            total_str = f"{self._total_bytes / 1024:.1f} KB"

        self.stats_updated.emit(speed_str, total_str)