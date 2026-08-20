from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.settings.detector import detect_system_proxy
from app.settings.models import ProxySettings


class ProxySettingsSection(QWidget):
    """Encapsulated UI component managing Telegram Proxy configuration."""

    proxy_saved = Signal(object)  # Emits ProxySettings

    def __init__(self, current_settings: ProxySettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_settings = current_settings
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title = QLabel("🛡️ تنظیمات پروکسی تلگرام (رمزنگاری‌شده)")
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #6ab3f3;")
        layout.addWidget(title)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("بدون پروکسی (اتصال مستقیم / Direct)", "DIRECT")
        self.mode_combo.addItem("استفاده از پروکسی سیستم (System Proxy)", "SYSTEM")
        self.mode_combo.addItem("پروکسی دستی (Custom SOCKS5 / HTTP)", "CUSTOM")

        idx = self.mode_combo.findData(self._current_settings.mode)
        self.mode_combo.setCurrentIndex(idx if idx != -1 else 0)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        layout.addWidget(self.mode_combo)

        self.status_hint = QLabel()
        self.status_hint.setWordWrap(True)
        self.status_hint.setStyleSheet("font-size: 11px; color: #7f91a4; margin: 2px 0;")
        layout.addWidget(self.status_hint)

        self.manual_frame = QFrame()
        form = QFormLayout(self.manual_frame)
        form.setContentsMargins(0, 4, 0, 4)
        form.setSpacing(8)

        self.proxy_type = QComboBox()
        self.proxy_type.addItems(["SOCKS5", "HTTP"])
        self.proxy_type.setCurrentText(self._current_settings.proxy_type)

        self.server_input = QLineEdit(self._current_settings.server)
        self.server_input.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        self.port_input = QLineEdit(str(self._current_settings.port))
        self.port_input.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        form.addRow("نوع پروتکل:", self.proxy_type)
        form.addRow("آدرس سرور:", self.server_input)
        form.addRow("پورت:", self.port_input)
        layout.addWidget(self.manual_frame)

        btn_save = QPushButton("ذخیره و فعال‌سازی پروکسی")
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.clicked.connect(self._on_save)
        layout.addWidget(btn_save)

        self._on_mode_changed()

    def _on_mode_changed(self) -> None:
        mode = self.mode_combo.currentData()
        if mode == "DIRECT":
            self.manual_frame.hide()
            self.status_hint.setText("🌐 اتصال مستقیم بدون پروکسی برقرار می‌شود.")
            self.status_hint.setStyleSheet("color: #7f91a4; font-size: 11px;")
        elif mode == "SYSTEM":
            self.manual_frame.hide()
            sys_proxy = detect_system_proxy()
            if sys_proxy:
                ptype, host, port, _, _ = sys_proxy
                self.status_hint.setText(f"✅ پروکسی سیستم شناسایی شد: {ptype}://{host}:{port}")
                self.status_hint.setStyleSheet("color: #4fae4e; font-size: 11px; font-weight: bold;")
            else:
                self.status_hint.setText("⚠️ پروکسی فعالی روی سیستم‌عامل شناسایی نشد (اتصال مستقیم برقرار می‌شود).")
                self.status_hint.setStyleSheet("color: #e6a23c; font-size: 11px;")
        elif mode == "CUSTOM":
            self.manual_frame.show()
            self.status_hint.setText("⚙️ مشخصات پروکسی SOCKS5 یا HTTP خود را وارد کنید:")
            self.status_hint.setStyleSheet("color: #6ab3f3; font-size: 11px;")

    def _on_save(self) -> None:
        mode = self.mode_combo.currentData()
        server = self.server_input.text().strip() or "127.0.0.1"
        port_txt = self.port_input.text().strip()
        port = int(port_txt) if port_txt.isdigit() else 10808

        settings = ProxySettings(
            mode=mode,
            enabled=(mode != "DIRECT"),
            proxy_type=self.proxy_type.currentText(),
            server=server,
            port=port,
        )
        self.proxy_saved.emit(settings)