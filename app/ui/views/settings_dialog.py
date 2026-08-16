from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.cache.service import CacheService
from app.settings.service import SettingsService


class SettingsDialog(QDialog):
    """Settings, Proxy and Cache management dialog."""

    cache_cleared = Signal()
    proxy_saved = Signal(str, str, int)

    def __init__(
        self,
        cache_service: CacheService,
        settings_service: SettingsService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._cache = cache_service
        self._settings = settings_service

        self.setWindowTitle("تنظیمات TMusic")
        self.resize(420, 360)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #17212b;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
                font-family: 'Vazirmatn', 'Segoe UI', sans-serif;
            }
            QLineEdit, QComboBox {
                padding: 6px 10px;
                border: 1px solid #2f3e50;
                border-radius: 6px;
                background-color: #242f3d;
                color: #ffffff;
                font-size: 13px;
            }
            QPushButton {
                background-color: #2481cc;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #1d72b8; }
            QPushButton#btnClear {
                background-color: #e53935;
            }
            QPushButton#btnClear:hover { background-color: #d32f2f; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 1. Proxy Section
        proxy_title = QLabel("🛡️ تنظیمات پروکسی تلگرام (رمزنگاری‌شده)")
        proxy_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #6ab3f3;")
        layout.addWidget(proxy_title)

        form = QFormLayout()
        form.setSpacing(8)

        self.proxy_type = QComboBox()
        self.proxy_type.addItems(["SOCKS5", "HTTP"])
        self.proxy_type.setCurrentText(self._settings.preferences.proxy.proxy_type)

        self.proxy_server = QLineEdit()
        self.proxy_server.setText(self._settings.preferences.proxy.server)
        self.proxy_server.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        self.proxy_port = QLineEdit()
        self.proxy_port.setText(str(self._settings.preferences.proxy.port))
        self.proxy_port.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        form.addRow("نوع پروکسی:", self.proxy_type)
        form.addRow("آدرس سرور (IP):", self.proxy_server)
        form.addRow("پورت (Port):", self.proxy_port)
        layout.addLayout(form)

        btn_save_proxy = QPushButton("ذخیره و اعمال پروکسی")
        btn_save_proxy.clicked.connect(self._on_save_proxy)
        layout.addWidget(btn_save_proxy)

        # Separator line
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #242f3d;")
        layout.addWidget(sep)

        # 2. Cache Section
        cache_title = QLabel("💾 مدیریت حافظه موقت (کش)")
        cache_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #6ab3f3;")
        layout.addWidget(cache_title)

        cache_layout = QHBoxLayout()
        cache_label = QLabel("حجم آهنگ‌های ذخیره‌شده:")
        self.size_val = QLabel(self._cache.get_formatted_cache_size())
        self.size_val.setStyleSheet("font-weight: bold; color: #4fae4e;")

        cache_layout.addWidget(cache_label)
        cache_layout.addStretch()
        cache_layout.addWidget(self.size_val)
        layout.addLayout(cache_layout)

        btn_clear = QPushButton("🗑️ پاک‌سازی کش آهنگ‌ها")
        btn_clear.setObjectName("btnClear")
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.clicked.connect(self._on_clear_cache)
        layout.addWidget(btn_clear)

        layout.addStretch()

        # Close button
        btn_close = QPushButton("بستن")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def _on_save_proxy(self) -> None:
        ptype = self.proxy_type.currentText()
        server = self.proxy_server.text().strip() or "127.0.0.1"
        port_txt = self.proxy_port.text().strip()
        port = int(port_txt) if port_txt.isdigit() else 10808

        self._settings.set_proxy(ptype, server, port, enabled=True)
        self.proxy_saved.emit(ptype, server, port)

    def _on_clear_cache(self) -> None:
        self._cache.clear_cache()
        self.size_val.setText(self._cache.get_formatted_cache_size())
        self.cache_cleared.emit()