import atexit
import logging
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path
import queue
import sys

from app.config import AppConfig

# Rotation limits
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MiB
LOG_BACKUP_COUNT = 3


def setup_logging(config: AppConfig, is_dev: bool = True) -> logging.Logger:
    """Initialize central thread-safe queue-based logging."""
    log_dir = config.root_dir / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "tmusic.log"

    # Common formatter
    log_format = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s:%(threadName)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 1. Rotating File Handler
    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(log_format)

    # 2. Console Handler for Development
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)

    # Handlers managed by the QueueListener (runs in its own thread)
    handlers = [file_handler, console_handler] if is_dev else [file_handler]

    # Queue pipeline setup
    log_queue: queue.Queue[logging.LogRecord] = queue.Queue(maxsize=10_000)
    queue_handler = QueueHandler(log_queue)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if is_dev else logging.INFO)
    root_logger.addHandler(queue_handler)

    listener = QueueListener(log_queue, *handlers, respect_handler_level=True)
    listener.start()

    # Ensure clean shutdown
    atexit.register(listener.stop)

    logger = logging.getLogger("tmusic.bootstrap")
    logger.info("Logging system initialized. Log file: %s", log_file)
    return logger