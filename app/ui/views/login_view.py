from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import AppConfig
from app.settings.service import ProxySettings
from app.ui.utils.icons import get_app_logo_pixmap, get_svg_icon
from app.ui.views.proxy_dialog import ProxyDialog


class LoginView(QWidget):
    """
    Modern Telegram Desktop styled two-column authentication view with 100% transparent
    background labels, official vector logo, application version, author attribution, and auth card.
    """

    phone_submitted = Signal(str)
    code_submitted = Signal(str)
    password_submitted = Signal(str)
    proxy_configured = Signal(object)

    def __init__(self, config: AppConfig | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config or AppConfig()
        self._current_proxy_settings = ProxySettings()
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.setStyleSheet("""
            LoginView {
                background-color: #0e1621;
            }
            QLabel {
                background: transparent;
                background-color: transparent;
                border: none;
                font-family: 'Segoe UI', 'Vazirmatn', sans-serif;
            }
            QWidget {
                background: transparent;
                background-color: transparent;
            }
        """)
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 16, 24, 24)
        main_layout.setSpacing(0)

        # 1. Top Bar: Connection Status & Proxy Button
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)

        self.conn_status_label = QLabel(self.tr("Status: Connecting..."), self)
        self.conn_status_label.setStyleSheet("background: transparent; color: #7f91a4; font-size: 12px; font-weight: 500;")

        btn_proxy = QPushButton(self.tr("Proxy Settings"), self)
        btn_proxy.setIcon(get_svg_icon("settings", "#6ab3f3", 14))
        btn_proxy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_proxy.setStyleSheet("""
            QPushButton {
                background: transparent;
                background-color: transparent;
                color: #6ab3f3;
                font-size: 12px;
                font-weight: bold;
                border: none;
                padding: 4px 8px;
            }
            QPushButton:hover {
                text-decoration: underline;
                color: #52a3ff;
            }
        """)
        btn_proxy.clicked.connect(self._open_proxy_dialog)

        top_bar.addWidget(self.conn_status_label)
        top_bar.addStretch()
        top_bar.addWidget(btn_proxy)
        main_layout.addLayout(top_bar)

        # 2. Main Two-Column Center Container
        center_wrapper = QWidget(self)
        center_layout = QHBoxLayout(center_wrapper)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(48)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # --- Left Column: App Logo, Version & Author Attribution ---
        branding_side = QWidget(center_wrapper)
        branding_side.setFixedWidth(320)
        b_layout = QVBoxLayout(branding_side)
        b_layout.setContentsMargins(10, 10, 10, 10)
        b_layout.setSpacing(10)
        b_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Large Vector App Logo
        self.logo_label = QLabel(branding_side)
        self.logo_label.setFixedSize(140, 140)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_label.setPixmap(get_app_logo_pixmap(size=140))
        self.logo_label.setStyleSheet("background: transparent; background-color: transparent; border: none;")

        # Application Title
        app_title = QLabel(self._config.app_name, branding_side)
        app_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_title.setStyleSheet("background: transparent; background-color: transparent; border: none; color: #ffffff; font-size: 26px; font-weight: bold; letter-spacing: 0.5px;")

        # Subtitle Tagline
        app_subtitle = QLabel(self.tr("Fast & Native Telegram Music Player"), branding_side)
        app_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_subtitle.setWordWrap(True)
        app_subtitle.setStyleSheet("background: transparent; background-color: transparent; border: none; color: #7f91a4; font-size: 12px;")

        # Version Badge
        version_badge = QLabel(f"Version {self._config.app_version}", branding_side)
        version_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_badge.setStyleSheet("""
            background-color: #17212b;
            color: #6ab3f3;
            font-size: 11px;
            font-weight: bold;
            padding: 4px 12px;
            border-radius: 10px;
            border: 1px solid #242f3d;
        """)

        # Developer Attribution
        author_label = QLabel(f"Developed by {self._config.auther}", branding_side)
        author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        author_label.setStyleSheet("background: transparent; background-color: transparent; border: none; color: #5d6e80; font-size: 11px; font-weight: bold; margin-top: 4px;")

        b_layout.addWidget(self.logo_label, alignment=Qt.AlignmentFlag.AlignCenter)
        b_layout.addWidget(app_title, alignment=Qt.AlignmentFlag.AlignCenter)
        b_layout.addWidget(app_subtitle, alignment=Qt.AlignmentFlag.AlignCenter)
        b_layout.addSpacing(6)
        b_layout.addWidget(version_badge, alignment=Qt.AlignmentFlag.AlignCenter)
        b_layout.addWidget(author_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Vertical Divider Line
        divider = QFrame(center_wrapper)
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFixedHeight(340)
        divider.setStyleSheet("color: #1f2b38; background-color: #1f2b38;")

        # --- Right Column: Telegram Authentication Card ---
        card = QFrame(center_wrapper)
        card.setObjectName("loginCard")
        card.setFixedWidth(380)
        card.setStyleSheet("""
            QFrame#loginCard {
                background-color: #17212b;
                border: 1.5px solid #242f3d;
                border-radius: 14px;
            }
            QLabel {
                font-family: 'Segoe UI', 'Vazirmatn', sans-serif;
                color: #ffffff;
                background: transparent;
                background-color: transparent;
                border: none;
            }
            QWidget {
                background: transparent;
                background-color: transparent;
            }
            QLineEdit {
                padding: 10px 14px;
                border: 1.5px solid #2f3e50;
                border-radius: 8px;
                font-size: 13px;
                background-color: #242f3d;
                color: #ffffff;
            }
            QLineEdit:focus {
                border-color: #2481cc;
                background-color: #1c2734;
            }
            QPushButton {
                background-color: #2481cc;
                color: #ffffff;
                font-size: 13px;
                font-weight: bold;
                padding: 10px;
                border-radius: 8px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1d72b8;
            }
            QPushButton:disabled {
                background-color: #1c3d5a;
                color: #4a6a8a;
            }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 28, 28, 28)
        card_layout.setSpacing(16)

        title_label = QLabel(self.tr("Log In to Telegram"), card)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("background: transparent; border: none; font-size: 18px; font-weight: bold; color: #6ab3f3;")
        card_layout.addWidget(title_label)

        self.error_label = QLabel("", card)
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setStyleSheet("background: transparent; border: none; color: #e53935; font-size: 12px;")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        card_layout.addWidget(self.error_label)

        self.stack = QStackedWidget(card)

        # Step 1: Phone Step
        phone_page = QWidget(self.stack)
        phone_layout = QVBoxLayout(phone_page)
        phone_layout.setContentsMargins(0, 0, 0, 0)
        phone_layout.setSpacing(14)

        desc_phone = QLabel(self.tr("Enter your country code and phone number:"), phone_page)
        desc_phone.setWordWrap(True)
        desc_phone.setStyleSheet("background: transparent; border: none; font-size: 12px; color: #7f91a4;")

        inputs_container = QWidget(phone_page)
        inputs_row = QHBoxLayout(inputs_container)
        inputs_row.setContentsMargins(0, 0, 0, 0)
        inputs_row.setSpacing(8)

        self.country_code_input = QLineEdit("+1", inputs_container)
        self.country_code_input.setFixedWidth(80)
        self.country_code_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.country_code_input.returnPressed.connect(self._on_country_code_enter)

        self.phone_number_input = QLineEdit(inputs_container)
        self.phone_number_input.setPlaceholderText(self.tr("Phone number"))
        self.phone_number_input.returnPressed.connect(self._on_submit_phone)

        inputs_row.addWidget(self.country_code_input)
        inputs_row.addWidget(self.phone_number_input)

        self.btn_phone = QPushButton(self.tr("Continue"), phone_page)
        self.btn_phone.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_phone.clicked.connect(self._on_submit_phone)

        phone_layout.addWidget(desc_phone)
        phone_layout.addWidget(inputs_container)
        phone_layout.addWidget(self.btn_phone)

        # Step 2: Verification Code Step
        code_page = QWidget(self.stack)
        code_layout = QVBoxLayout(code_page)
        code_layout.setContentsMargins(0, 0, 0, 0)
        code_layout.setSpacing(12)

        desc_code = QLabel(self.tr("Enter the verification code sent to your Telegram app:"), code_page)
        desc_code.setWordWrap(True)
        desc_code.setStyleSheet("background: transparent; border: none; font-size: 12px; color: #7f91a4;")

        self.code_input = QLineEdit(code_page)
        self.code_input.setPlaceholderText(self.tr("Code"))
        self.code_input.returnPressed.connect(self._on_submit_code)

        self.btn_code = QPushButton(self.tr("Confirm Code"), code_page)
        self.btn_code.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_code.clicked.connect(self._on_submit_code)

        code_layout.addWidget(desc_code)
        code_layout.addWidget(self.code_input)
        code_layout.addWidget(self.btn_code)

        # Step 3: 2FA Password Step
        pwd_page = QWidget(self.stack)
        pwd_layout = QVBoxLayout(pwd_page)
        pwd_layout.setContentsMargins(0, 0, 0, 0)
        pwd_layout.setSpacing(12)

        desc_pwd = QLabel(self.tr("Enter your Two-Step Verification cloud password:"), pwd_page)
        desc_pwd.setWordWrap(True)
        desc_pwd.setStyleSheet("background: transparent; border: none; font-size: 12px; color: #7f91a4;")

        self.pwd_input = QLineEdit(pwd_page)
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_input.setPlaceholderText(self.tr("Password"))
        self.pwd_input.returnPressed.connect(self._on_submit_password)

        self.btn_pwd = QPushButton(self.tr("Log In"), pwd_page)
        self.btn_pwd.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pwd.clicked.connect(self._on_submit_password)

        pwd_layout.addWidget(desc_pwd)
        pwd_layout.addWidget(self.pwd_input)
        pwd_layout.addWidget(self.btn_pwd)

        self.stack.addWidget(phone_page)
        self.stack.addWidget(code_page)
        self.stack.addWidget(pwd_page)

        card_layout.addWidget(self.stack)

        center_layout.addWidget(branding_side)
        center_layout.addWidget(divider)
        center_layout.addWidget(card)

        main_layout.addStretch(1)
        main_layout.addWidget(center_wrapper)
        main_layout.addStretch(1)

    def set_connection_status(self, state: str) -> None:
        match state:
            case "connectionStateReady":
                self.conn_status_label.setText(self.tr("Status: Connected"))
                self.conn_status_label.setStyleSheet("background: transparent; border: none; color: #4fae4e; font-size: 12px; font-weight: 500;")
            case "connectionStateConnectingToProxy":
                self.conn_status_label.setText(self.tr("Status: Connecting to proxy..."))
                self.conn_status_label.setStyleSheet("background: transparent; border: none; color: #e6a23c; font-size: 12px; font-weight: 500;")
            case "connectionStateConnecting":
                self.conn_status_label.setText(self.tr("Status: Connecting to Telegram..."))
                self.conn_status_label.setStyleSheet("background: transparent; border: none; color: #e6a23c; font-size: 12px; font-weight: 500;")
            case "connectionStateWaitingForNetwork":
                self.conn_status_label.setText(self.tr("Status: Waiting for network"))
                self.conn_status_label.setStyleSheet("background: transparent; border: none; color: #e53935; font-size: 12px; font-weight: 500;")

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