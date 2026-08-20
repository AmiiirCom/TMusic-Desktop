import argparse
import logging
import os
import sys

from app.bootstrap import create_application
from app.cache.service import CacheManager
from app.config import AppConfig
from app.core.logger import setup_logging
from app.core.security import CryptoManager
from app.network.meter import NetworkMeter
from app.network.stream_server import LocalStreamServer
from app.player.service import PlayerService
from app.settings.service import SettingsService
from app.telegram.adapter import TDLibAdapter
from app.telegram.service import TelegramService
from app.ui.main_window import MainWindow

logger = logging.getLogger("tmusic.main")


def resolve_log_level(args: argparse.Namespace) -> int:
    is_frozen = getattr(sys, "frozen", False)
    default_level = logging.WARNING if is_frozen else logging.INFO

    if args.log_level:
        return getattr(logging, args.log_level.upper())
    elif args.debug:
        return logging.DEBUG

    env_level = os.environ.get("TMUSIC_LOG_LEVEL", "").upper()
    if env_level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        return getattr(logging, env_level)

    return default_level


def main() -> int:
    config = AppConfig()

    parser = argparse.ArgumentParser(description="TMusic Desktop")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    args, _ = parser.parse_known_args()

    setup_logging(config, log_level=resolve_log_level(args), console_level=logging.WARNING)
    logger.info("Starting %s v%s...", config.app_name, config.app_version)

    app = create_application(config)

    crypto_manager = CryptoManager(config.app_data_dir)
    settings_service = SettingsService(config, crypto_manager)

    tdlib_adapter = TDLibAdapter()
    stream_server = LocalStreamServer(tdlib_adapter)
    cache_manager = CacheManager(config, crypto_manager, tdlib_adapter)

    telegram_service = TelegramService(config, tdlib_adapter, settings_service, cache_manager)
    player_service = PlayerService(config, telegram_service, settings_service, cache_manager, stream_server)
    network_meter = NetworkMeter()

    window = MainWindow(
        config=config,
        telegram_service=telegram_service,
        player_service=player_service,
        cache_manager=cache_manager,
        network_meter=network_meter,
        settings_service=settings_service,
        stream_server=stream_server,
        tdlib_adapter=tdlib_adapter,
    )
    window.show()

    telegram_service.start()
    exit_code = app.exec()

    stream_server.stop()
    telegram_service.stop()
    tdlib_adapter.close()
    logger.info("Application exited with code %d", exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())