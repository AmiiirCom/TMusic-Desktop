from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.settings.service import ProxySettings
from app.ui.views.proxy_dialog import ProxyDialog


class LoginView(QWidget):
    """Telegram-styled authentication widget with clean English labels."""

    phone_submitted = Signal(str)
    code_submitted = Signal(str)
    password_submitted = Signal(str)
    proxy_configured = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_proxy_settings = ProxySettings()
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Top Bar
        top_bar = QHBoxLayout()
        self.conn_status_label = QLabel(self.tr("Status: Connecting..."))
        self.conn_status_label.setStyleSheet("color: #707579; font-size: 12px;")

        btn_proxy = QPushButton(self.tr("Proxy Settings"))
        btn_proxy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_proxy.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #2481cc;
                font-size: 12px;
                font-weight: bold;
                border: none;
                padding: 4px 8px;
            }
            QPushButton:hover { text-decoration: underline; }
        """)
        btn_proxy.clicked.connect(self._open_proxy_dialog)

        top_bar.addWidget(self.conn_status_label)
        top_bar.addStretch()
        top_bar.addWidget(btn_proxy)
        main_layout.addLayout(top_bar)

        # Card container
        card = QWidget(self)
        card.setFixedWidth(400)
        card.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                border-radius: 12px;
            }
            QLabel {
                font-family: 'Segoe UI', sans-serif;
                color: #222222;
            }
            QLineEdit {
                padding: 10px 12px;
                border: 1.5px solid #dfe1e5;
                border-radius: 8px;
                font-size: 14px;
                background-color: #f7f9fa;
                color: #222222;
            }
            QLineEdit:focus {
                border-color: #2481cc;
                background-color: #ffffff;
            }
            QPushButton {
                background-color: #2481cc;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 8px;
                border: none;
            }
            QPushButton:hover { background-color: #1d72b8; }
            QPushButton:disabled { background-color: #a0c3e8; }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 32, 28, 32)
        card_layout.setSpacing(16)

        title_label = QLabel(self.tr("Log In to Telegram"))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #2481cc;")
        card_layout.addWidget(title_label)

        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setStyleSheet("color: #e53935; font-size: 12px;")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        card_layout.addWidget(self.error_label)

        self.stack = QStackedWidget(self)

        # 1. Phone Step
        phone_page = QWidget()
        phone_layout = QVBoxLayout(phone_page)
        phone_layout.setContentsMargins(0, 0, 0, 0)
        phone_layout.setSpacing(14)

        desc_phone = QLabel(self.tr("Enter your country code and phone number:"))
        desc_phone.setWordWrap(True)
        desc_phone.setStyleSheet("font-size: 13px; color: #707579;")

        inputs_container = QWidget(phone_page)
        inputs_row = QHBoxLayout(inputs_container)
        inputs_row.setContentsMargins(0, 0, 0, 0)
        inputs_row.setSpacing(8)

        self.country_code_input = QLineEdit("+1")
        self.country_code_input.setFixedWidth(80)
        self.country_code_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.country_code_input.returnPressed.connect(self._on_country_code_enter)

        self.phone_number_input = QLineEdit()
        self.phone_number_input.setPlaceholderText(self.tr("Phone number"))
        self.phone_number_input.returnPressed.connect(self._on_submit_phone)

        inputs_row.addWidget(self.country_code_input)
        inputs_row.addWidget(self.phone_number_input)

        self.btn_phone = QPushButton(self.tr("Continue"))
        self.btn_phone.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_phone.clicked.connect(self._on_submit_phone)

        phone_layout.addWidget(desc_phone)
        phone_layout.addWidget(inputs_container)
        phone_layout.addWidget(self.btn_phone)

        # 2. Code Step
        code_page = QWidget()
        code_layout = QVBoxLayout(code_page)
        code_layout.setContentsMargins(0, 0, 0, 0)
        code_layout.setSpacing(12)

        desc_code = QLabel(self.tr("Enter the verification code sent to your Telegram app:"))
        desc_code.setWordWrap(True)
        desc_code.setStyleSheet("font-size: 13px; color: #707579;")
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText(self.tr("Code"))
        self.code_input.returnPressed.connect(self._on_submit_code)

        self.btn_code = QPushButton(self.tr("Confirm Code"))
        self.btn_code.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_code.clicked.connect(self._on_submit_code)

        code_layout.addWidget(desc_code)
        code_layout.addWidget(self.code_input)
        code_layout.addWidget(self.btn_code)

        # 3. 2FA Password Step
        pwd_page = QWidget()
        pwd_layout = QVBoxLayout(pwd_page)
        pwd_layout.setContentsMargins(0, 0, 0, 0)
        pwd_layout.setSpacing(12)

        desc_pwd = QLabel(self.tr("Enter your Two-Step Verification cloud password:"))
        desc_pwd.setWordWrap(True)
        desc_pwd.setStyleSheet("font-size: 13px; color: #707579;")
        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_input.setPlaceholderText(self.tr("Password"))
        self.pwd_input.returnPressed.connect(self._on_submit_password)

        self.btn_pwd = QPushButton(self.tr("Log In"))
        self.btn_pwd.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pwd.clicked.connect(self._on_submit_password)

        pwd_layout.addWidget(desc_pwd)
        pwd_layout.addWidget(self.pwd_input)
        pwd_layout.addWidget(self.btn_pwd)

        self.stack.addWidget(phone_page)
        self.stack.addWidget(code_page)
        self.stack.addWidget(pwd_page)

        card_layout.addWidget(self.stack)
        main_layout.addWidget(card)

    def set_connection_status(self, state: str) -> None:
        match state:
            case "connectionStateReady":
                self.conn_status_label.setText(self.tr("Status: Connected"))
                self.conn_status_label.setStyleSheet("color: #4fae4e; font-size: 12px;")
            case "connectionStateConnectingToProxy":
                self.conn_status_label.setText(self.tr("Status: Connecting to proxy..."))
                self.conn_status_label.setStyleSheet("color: #e6a23c; font-size: 12px;")
            case "connectionStateConnecting":
                self.conn_status_label.setText(self.tr("Status: Connecting to Telegram..."))
                self.conn_status_label.setStyleSheet("color: #e6a23c; font-size: 12px;")
            case "connectionStateWaitingForNetwork":
                self.conn_status_label.setText(self.tr("Status: Waiting for network"))
                self.conn_status_label.setStyleSheet("color: #e53935; font-size: 12px;")

    def _open_proxy_dialog(self) -> None:
        dialog = ProxyDialog(parent=self.window(), current_settings=self._current_proxy_settings)
        dialog.proxy_applied.connect(self._on_proxy_dialog_applied)
        dialog.exec()

    def _on_proxy_dialog_applied(self, settings: ProxySettings) -> None:
        self._current_proxy_settings = settings
        self.proxy_configured.emit(settings)

    def show_phone_step(self) -> None:
        self._reset_buttons()
        self.error_label.hide()
        self.stack.setCurrentIndex(0)
        self.phone_number_input.setFocus()

    def show_code_step(self) -> None:
        self._reset_buttons()
        self.error_label.hide()
        self.stack.setCurrentIndex(1)
        self.code_input.setFocus()

    def show_password_step(self) -> None:
        self._reset_buttons()
        self.error_label.hide()
        self.stack.setCurrentIndex(2)
        self.pwd_input.setFocus()

    def show_error(self, message: str) -> None:
        self._reset_buttons()
        self.error_label.setText(message)
        self.error_label.show()

    def _reset_buttons(self) -> None:
        self.btn_phone.setEnabled(True)
        self.btn_phone.setText(self.tr("Continue"))
        self.btn_code.setEnabled(True)
        self.btn_code.setText(self.tr("Confirm Code"))
        self.btn_pwd.setEnabled(True)
        self.btn_pwd.setText(self.tr("Log In"))

    def _on_country_code_enter(self) -> None:
        self.phone_number_input.setFocus()

    def _on_submit_phone(self) -> None:
        code = self.country_code_input.text().strip()
        number = self.phone_number_input.text().strip()

        if not code or not number:
            self.show_error(self.tr("Please enter both country code and phone number."))
            return

        if not code.startswith("+"):
            code = f"+{code}"

        clean_number = number.lstrip("0")
        full_phone = f"{code}{clean_number}"

        self.btn_phone.setEnabled(False)
        self.btn_phone.setText(self.tr("Sending..."))
        self.phone_submitted.emit(full_phone)

    def _on_submit_code(self) -> None:
        text = self.code_input.text().strip()
        if text:
            self.btn_code.setEnabled(False)
            self.btn_code.setText(self.tr("Checking..."))
            self.code_submitted.emit(text)

    def _on_submit_password(self) -> None:
        text = self.pwd_input.text()
        if text:
            self.btn_pwd.setEnabled(False)
            self.btn_pwd.setText(self.tr("Logging in..."))
            self.password_submitted.emit(text)