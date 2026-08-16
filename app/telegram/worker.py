import logging
from typing import Any
from PySide6.QtCore import QThread, Signal

from app.telegram.adapter import TDLibAdapter

logger = logging.getLogger("tmusic.telegram.worker")


class TDLibWorker(QThread):
    """Background worker thread dedicated to running the TDLib receive loop."""

    update_received = Signal(dict)
    stopped = Signal()

    def __init__(self, adapter: TDLibAdapter) -> None:
        super().__init__()
        self._adapter = adapter
        self._running = False

    def run(self) -> None:
        """Main receive loop running in background."""
        self._running = True
        logger.info("TDLib worker thread started")

        while self._running:
            try:
                update = self._adapter.receive(timeout=0.5)
                if update is not None:
                    # Emit update safely to GUI thread via Qt Signal
                    self.update_received.emit(update)
            except Exception as exc:
                logger.exception("Error in TDLib receive loop: %s", exc)

        logger.info("TDLib worker thread stopped")
        self.stopped.emit()

    def stop(self) -> None:
        """Signal the worker thread to stop cleanly."""
        logger.info("Stopping TDLib worker...")
        self._running = False
        self.wait(2000)