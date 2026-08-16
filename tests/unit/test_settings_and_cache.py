from dataclasses import dataclass
from pathlib import Path
from app.cache.service import CacheService
from app.core.security import CryptoManager
from app.settings.service import SettingsService


def test_settings_persistence(tmp_path: Path) -> None:
    """Verify that user preferences and proxy persist encrypted and reload cleanly."""
    crypto = CryptoManager(tmp_path)
    settings = SettingsService(tmp_path, crypto)

    # Change settings
    settings.set_proxy(proxy_type="HTTP", server="192.168.1.50", port=8080, enabled=True)
    settings.set_volume(45)
    settings.set_last_chat(123456789)

    # Create a fresh service instance reading the same encrypted file
    new_settings_instance = SettingsService(tmp_path, crypto)

    assert new_settings_instance.preferences.volume == 45
    assert new_settings_instance.preferences.last_chat_id == 123456789
    assert new_settings_instance.preferences.proxy.server == "192.168.1.50"
    assert new_settings_instance.preferences.proxy.port == 8080
    assert new_settings_instance.preferences.proxy.proxy_type == "HTTP"


def test_cache_calculation_and_clear(tmp_path: Path) -> None:
    """Verify cache size calculation and file deletion."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    # Create dummy media files
    file1 = cache_dir / "track1.mp3"
    file1.write_bytes(b"A" * 1024 * 1024)  # 1 MB

    file2 = cache_dir / "track2.mp3"
    file2.write_bytes(b"B" * (512 * 1024))  # 0.5 MB

    @dataclass(slots=True)
    class MockConfig:
        root_dir: Path
        cache_dir: Path

    mock_config = MockConfig(root_dir=tmp_path, cache_dir=cache_dir)
    cache_service = CacheService(mock_config)  # type: ignore

    total_bytes = cache_service.get_cache_size_bytes()
    assert total_bytes == int(1.5 * 1024 * 1024)

    # Clear cache
    cache_service.clear_cache()
    assert cache_service.get_cache_size_bytes() == 0
    assert not file1.exists()
    assert not file2.exists()