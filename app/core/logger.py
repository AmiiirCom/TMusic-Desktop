import atexit
import logging
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path
import queue
import sys
import threading
from typing import Any

from app.config import AppConfig

LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MiB
LOG_BACKUP_COUNT = 3

def setup_logging(config: AppConfig, is_dev: bool = True) -> logging.Logger:
    log_dir = config.app_data_dir / "log"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        log_dir = Path.home() / ".tmusic_log"
        log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "tmusic.log"

    log_format = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s:%(threadName)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(log_format)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)

    handlers = [file_handler, console_handler] if is_dev else [file_handler]

    log_queue: queue.Queue[logging.LogRecord] = queue.Queue(maxsize=10_000)
    queue_handler = QueueHandler(log_queue)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if is_dev else logging.INFO)
    root_logger.addHandler(queue_handler)

    listener = QueueListener(log_queue, *handlers, respect_handler_level=True)
    listener.start()

    atexit.register(listener.stop)

    def handle_main_exception(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: Any,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        root_logger.critical(
            "Uncaught main thread exception",
            exc_info=exc_value,
        )

    def handle_thread_exception(args: threading.ExceptHookArgs) -> None:
        if args.exc_type and issubclass(args.exc_type, KeyboardInterrupt):
            return
        thread_name = args.thread.name if args.thread else "UnknownThread"
        root_logger.critical(
            "Uncaught background thread exception in %s",
            thread_name,
            exc_info=args.exc_value,
        )

    sys.excepthook = handle_main_exception
    threading.excepthook = handle_thread_exception

    logger = logging.getLogger("tmusic.bootstrap")
    logger.info("Logging system initialized. Log file: %s", log_file)
    return logger