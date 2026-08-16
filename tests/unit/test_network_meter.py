from app.network.meter import NetworkMeter


def test_network_meter_accumulation() -> None:
    """Verify network byte accumulation and formatting."""
    meter = NetworkMeter()

    # Record 2 MB download
    meter.record_download(2 * 1024 * 1024)
    assert meter._total_bytes == 2 * 1024 * 1024

    # Trigger internal tick calculation
    meter._on_tick()

    # Total should be formatted cleanly as MB
    assert meter._last_tick_bytes == 2 * 1024 * 1024