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


class ProxyDialog(QDialog):
    """Telegram Desktop styled Proxy settings dialog."""

    proxy_applied = Signal(str, str, int)  # type, server, port

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("تنظیمات پروکسی تلگرام")
        self.resize(360, 240)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #212d3b;
                color: #ffffff;
            }
            QLabel {
                color: #e4ecf2;
                font-size: 13px;
            }
            QLineEdit, QComboBox {
                padding: 8px 12px;
                border: 1px solid #2f3e50;
                border-radius: 6px;
                background-color: #17212b;
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
            QPushButton#btnCancel {
                background-color: transparent;
                color: #6ab3f3;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

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
        self.port_input.setText("10808")  # Default port for v2ray/xray
        self.port_input.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        form.addRow("نوع پروکسی:", self.type_combo)
        form.addRow("آدرس سرور (IP):", self.server_input)
        form.addRow("پورت (Port):", self.port_input)

        layout.addLayout(form)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("ذخیره و اتصال")
        btn_save.clicked.connect(self._on_save)

        btn_cancel = QPushButton("انصراف")
        btn_cancel.setObjectName("btnCancel")
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def _on_save(self) -> None:
        server = self.server_input.text().strip() or "127.0.0.1"
        port_text = self.port_input.text().strip()
        port = int(port_text) if port_text.isdigit() else 10808
        proxy_type = self.type_combo.currentText()

        self.proxy_applied.emit(proxy_type, server, port)
        self.accept()