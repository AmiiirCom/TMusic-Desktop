from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.settings.service import ProxySettings, detect_system_proxy
from app.ui.views.base_modal import BaseModalDialog


class ProxyDialog(BaseModalDialog):
    """Telegram Desktop styled frameless Proxy settings dialog."""

    proxy_applied = Signal(object)

    def __init__(self, parent: QWidget | None = None, current_settings: ProxySettings | None = None) -> None:
        super().__init__(title="Telegram Proxy Settings", parent=parent)
        self.card_frame.setFixedWidth(420)
        self._current_settings = current_settings or ProxySettings()
        self._init_body()

    def _init_body(self) -> None:
        mode_layout = QVBoxLayout()
        mode_layout.setSpacing(4)

        mode_title = QLabel(self.tr("Connection Type:"))
        mode_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #6ab3f3;")
        mode_layout.addWidget(mode_title)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem(self.tr("Direct Connection"), "DIRECT")
        self.mode_combo.addItem(self.tr("System Proxy"), "SYSTEM")
        self.mode_combo.addItem(self.tr("Custom Proxy"), "CUSTOM")

        idx = self.mode_combo.findData(self._current_settings.mode)
        if idx != -1:
            self.mode_combo.setCurrentIndex(idx)
        else:
            self.mode_combo.setCurrentIndex(0)

        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        self.body_layout.addLayout(mode_layout)

        self.status_hint_label = QLabel()
        self.status_hint_label.setWordWrap(True)
        self.status_hint_label.setStyleSheet("font-size: 11px; color: #7f91a4; margin: 4px 0;")
        self.body_layout.addWidget(self.status_hint_label)

        self.manual_form_frame = QFrame()
        self.manual_form_frame.setStyleSheet("background-color: transparent;")
        form = QFormLayout(self.manual_form_frame)
        form.setContentsMargins(0, 4, 0, 4)
        form.setSpacing(8)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["SOCKS5", "HTTP"])
        self.type_combo.setCurrentText(self._current_settings.proxy_type)

        self.server_input = QLineEdit()
        self.server_input.setPlaceholderText("127.0.0.1")
        self.server_input.setText(self._current_settings.server)

        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("10808")
        self.port_input.setText(str(self._current_settings.port))

        form.addRow(self.tr("Protocol:"), self.type_combo)
        form.addRow(self.tr("Server:"), self.server_input)
        form.addRow(self.tr("Port:"), self.port_input)

        self.body_layout.addWidget(self.manual_form_frame)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 8, 0, 0)

        btn_save = QPushButton(self.tr("Save and Connect"))
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.clicked.connect(self._on_save)

        btn_cancel = QPushButton(self.tr("Cancel"))
        btn_cancel.setStyleSheet("background-color: transparent; color: #7f91a4;")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        self.body_layout.addLayout(btn_layout)

        self._on_mode_changed()

    def _on_mode_changed(self) -> None:
        selected_mode = self.mode_combo.currentData()

        if selected_mode == "DIRECT":
            self.manual_form_frame.hide()
            self.status_hint_label.setText(self.tr("Connecting directly without proxy."))
            self.status_hint_label.setStyleSheet("color: #7f91a4; font-size: 11px;")

        elif selected_mode == "SYSTEM":
            self.manual_form_frame.hide()
            sys_proxy = detect_system_proxy()
            if sys_proxy:
                ptype, host, port, _, _ = sys_proxy
                self.status_hint_label.setText(f"{self.tr('System proxy detected:')} {ptype}://{host}:{port}")
                self.status_hint_label.setStyleSheet("color: #4fae4e; font-size: 11px; font-weight: bold;")
            else:
                self.status_hint_label.setText(self.tr("No active system proxy detected."))
                self.status_hint_label.setStyleSheet("color: #e6a23c; font-size: 11px;")

        elif selected_mode == "CUSTOM":
            self.manual_form_frame.show()
            self.status_hint_label.setText(self.tr("Enter SOCKS5 or HTTP proxy parameters:"))
            self.status_hint_label.setStyleSheet("color: #6ab3f3; font-size: 11px;")

    def _on_save(self) -> None:
        mode = self.mode_combo.currentData()
        server = self.server_input.text().strip() or "127.0.0.1"
        port_text = self.port_input.text().strip()
        port = int(port_text) if port_text.isdigit() else 10808
        proxy_type = self.type_combo.currentText()

        settings = ProxySettings(
            mode=mode,
            enabled=(mode != "DIRECT"),
            proxy_type=proxy_type,
            server=server,
            port=port,
        )

        self.proxy_applied.emit(settings)
        self.accept()