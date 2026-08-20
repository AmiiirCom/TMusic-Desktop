from dataclasses import dataclass
from pathlib import Path
from app.config import AppConfig
from app.core.security import CryptoManager
from app.settings.service import ProxySettings, SettingsService, detect_system_proxy


def test_settings_persistence(tmp_path: Path) -> None:
    """Verify that user preferences, proxy modes, and save_to_downloads persist encrypted and reload cleanly."""
    crypto = CryptoManager(tmp_path)

    @dataclass(slots=True, frozen=True)
    class TestAppConfig(AppConfig):
        @property
        def app_data_dir(self) -> Path:
            return tmp_path

    config = TestAppConfig()
    settings = SettingsService(config, crypto)

    # Verify default mode on first start is DIRECT
    assert settings.preferences.proxy.mode == "DIRECT"
    assert settings.preferences.proxy.enabled is False

    # Set Custom proxy mode
    settings.set_proxy_settings(
        ProxySettings(
            mode="CUSTOM",
            enabled=True,
            proxy_type="HTTP",
            server="192.168.1.50",
            port=8080,
        )
    )
    settings.set_volume(45)
    settings.set_last_chat(123456789)
    settings.set_save_to_downloads(False)

    new_settings_instance = SettingsService(config, crypto)

    assert new_settings_instance.preferences.volume == 45
    assert new_settings_instance.preferences.last_chat_id == 123456789
    assert new_settings_instance.preferences.save_to_downloads is False
    assert new_settings_instance.preferences.proxy.mode == "CUSTOM"
    assert new_settings_instance.preferences.proxy.server == "192.168.1.50"
    assert new_settings_instance.preferences.proxy.port == 8080
    assert new_settings_instance.preferences.proxy.proxy_type == "HTTP"


def test_system_proxy_detection() -> None:
    """Verify detect_system_proxy function returns tuple or None without exceptions."""
    result = detect_system_proxy()
    if result is not None:
        assert isinstance(result, tuple)
        assert len(result) == 5
        assert result[0] in ("SOCKS5", "HTTP")
        assert isinstance(result[2], int)