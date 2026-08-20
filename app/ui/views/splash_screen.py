import logging
from typing import Callable
from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from app.config import AppConfig
from app.ui.utils.icons import get_app_logo_pixmap

logger = logging.getLogger("tmusic.ui.splash")


class SplashScreen(QWidget):
    """
    Polished, frameless animated launch screen displaying official vector logo,
    dynamic versioning, developer attribution, and hardware-accelerated opacity transitions.
    """

    finished = Signal()

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self._on_finish_callback: Callable[[], None] | None = None
        self._is_closing = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.SplashScreen
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(420, 310)

        # Set initial native window opacity for hardware-accelerated fade-in
        self.setWindowOpacity(0.0)

        self._init_ui()
        self._init_animations()

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Card container with sleek Telegram Dark styling
        self.card = QFrame(self)
        self.card.setObjectName("splashCard")
        self.card.setStyleSheet("""
            QFrame#splashCard {
                background-color: #17212b;
                border: 1.5px solid #242f3d;
                border-radius: 18px;
            }
            QLabel {
                font-family: 'Segoe UI', 'Vazirmatn', sans-serif;
            }
        """)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(28, 28, 28, 24)
        card_layout.setSpacing(8)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 1. Official Vector Application Logo
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(88, 88)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_label.setPixmap(get_app_logo_pixmap(size=88))

        # 2. Application Title
        title_label = QLabel(self._config.app_name)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #ffffff; font-size: 22px; font-weight: bold; letter-spacing: 0.5px;")

        # 3. Dynamic Application Version
        version_label = QLabel(f"Version {self._config.app_version}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #2481cc; font-size: 12px; font-weight: bold;")

        # 4. Animated Indeterminate Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setFixedWidth(220)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #242f3d;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2481cc, stop:0.5 #6ab3f3, stop:1 #2481cc);
                border-radius: 2px;
            }
        """)

        # 5. Creator Attribution
        creator_label = QLabel(f"Developed by {self._config.auther}")
        creator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        creator_label.setStyleSheet("color: #5d6e80; font-size: 11px; font-weight: bold; margin-top: 4px;")

        card_layout.addWidget(self.logo_label, alignment=Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(version_label, alignment=Qt.AlignmentFlag.AlignCenter)
        card_layout.addSpacing(6)
        card_layout.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(creator_label, alignment=Qt.AlignmentFlag.AlignCenter)

        root_layout.addWidget(self.card)

    def _init_animations(self) -> None:
        """Fade-in smoothly using native top-level window opacity."""
        self._fade_in_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_in_anim.setDuration(350)
        self._fade_in_anim.setStartValue(0.0)
        self._fade_in_anim.setEndValue(1.0)
        self._fade_in_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_in_anim.start()

    def finish_and_close(self, callback: Callable[[], None] | None = None, delay_ms: int = 1200) -> None:
        """Hold for a natural minimal duration, then smoothly fade out."""
        self._on_finish_callback = callback
        QTimer.singleShot(delay_ms, self._start_fade_out)

    def _start_fade_out(self) -> None:
        if self._is_closing:
            return
        self._is_closing = True

        self._fade_out_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_out_anim.setDuration(260)
        self._fade_out_anim.setStartValue(1.0)
        self._fade_out_anim.setEndValue(0.0)
        self._fade_out_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_out_anim.finished.connect(self._on_fade_out_completed)
        self._fade_out_anim.start()

    def _on_fade_out_completed(self) -> None:
        self.close()
        self.finished.emit()
        if self._on_finish_callback:
            self._on_finish_callback()