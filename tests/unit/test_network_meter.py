from app.network.meter import NetworkMeter, format_bytes, format_speed


def test_network_meter_precision_tracking() -> None:
    """Verify precision delta and speed calculations."""
    meter = NetworkMeter()

    # Initial baseline (e.g. 10 MB total before this app run)
    meter.update_network_stats(10 * 1024 * 1024, 1 * 1024 * 1024)
    assert meter._session_rx == 0
    assert meter._session_tx == 0

    # 1 second later: received 512 KB
    meter.update_network_stats(10 * 1024 * 1024 + 512 * 1024, 1 * 1024 * 1024 + 10 * 1024)
    assert meter._session_rx == 512 * 1024
    assert meter._session_tx == 10 * 1024

    # Format checks
    assert format_bytes(512 * 1024) == "512.0 KB"
    assert format_bytes(10 * 1024 * 1024) == "10.0 MB"
    assert format_speed(512 * 1024) == "512 KB/s"