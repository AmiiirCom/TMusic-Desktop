from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

from app.ui.views.base_modal import BaseModalDialog


class ProxyDialog(BaseModalDialog):
    """Telegram Desktop styled frameless Proxy settings dialog."""

    proxy_applied = Signal(str, str, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(title="تنظیمات پروکسی تلگرام", parent=parent)
        self.card_frame.setFixedWidth(380)
        self._init_body()

    def _init_body(self) -> None:
        form = QFormLayout()
        form.setSpacing(10)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["SOCKS5", "HTTP"])

        self.server_input = QLineEdit()
        self.server_input.setPlaceholderText("127.0.0.1")
        self.server_input.setText("127.0.0.1")
        self.server_input.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("10808")
        self.port_input.setText("10808")
        self.port_input.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        form.addRow("نوع پروکسی:", self.type_combo)
        form.addRow("آدرس سرور (IP):", self.server_input)
        form.addRow("پورت (Port):", self.port_input)

        self.body_layout.addLayout(form)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("ذخیره و اتصال")
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.clicked.connect(self._on_save)

        btn_cancel = QPushButton("انصراف")
        btn_cancel.setStyleSheet("background-color: transparent; color: #7f91a4;")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        self.body_layout.addLayout(btn_layout)

    def _on_save(self) -> None:
        server = self.server_input.text().strip() or "127.0.0.1"
        port_text = self.port_input.text().strip()
        port = int(port_text) if port_text.isdigit() else 10808
        proxy_type = self.type_combo.currentText()

        self.proxy_applied.emit(proxy_type, server, port)
        self.accept()