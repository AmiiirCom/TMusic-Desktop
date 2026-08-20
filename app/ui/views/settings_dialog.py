from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.cache.service import CacheManager
from app.config import AppConfig
from app.settings.service import SettingsService
from app.ui.views.base_modal import BaseModalDialog


class SettingsDialog(BaseModalDialog):
    """Clean, well-proportioned Settings, Proxy, and Storage management modal."""

    cache_cleared = Signal()
    proxy_saved = Signal(str, str, int)
    logout_requested = Signal()

    def __init__(
        self,
        cache_manager: CacheManager,
        settings_service: SettingsService,
        config: AppConfig,
        parent: QWidget | None = None,
    ) -> None:
        title = f"تنظیمات و حافظه {config.app_name}"
        super().__init__(title=title, parent=parent)
        self._cache = cache_manager
        self._settings = settings_service
        self._config = config
        self.card_frame.setFixedWidth(460)
        self._init_body()

    def _init_body(self) -> None:
        # Proxy Section
        proxy_title = QLabel("🛡️ تنظیمات پروکسی تلگرام (رمزنگاری‌شده)")
        proxy_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #6ab3f3;")
        self.body_layout.addWidget(proxy_title)

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
        form.addRow("آدرس سرور:", self.proxy_server)
        form.addRow("پورت:", self.proxy_port)
        self.body_layout.addLayout(form)

        btn_save_proxy = QPushButton("ذخیره و فعال‌سازی پروکسی")
        btn_save_proxy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save_proxy.clicked.connect(self._on_save_proxy)
        self.body_layout.addWidget(btn_save_proxy)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("color: #242f3d; margin: 4px 0;")
        self.body_layout.addWidget(sep1)

        # Storage & Download Settings
        storage_title = QLabel("📂 مدیریت دانلود و ذخیره‌سازی")
        storage_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #6ab3f3;")
        self.body_layout.addWidget(storage_title)

        # Save to Downloads Toggle
        self.save_downloads_checkbox = QCheckBox("ذخیره خودکار آهنگ‌ها در حافظه (پخش آفلاین)")
        self.save_downloads_checkbox.setChecked(self._settings.preferences.save_to_downloads)
        self.save_downloads_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_downloads_checkbox.toggled.connect(self._on_toggle_save_to_downloads)
        self.save_downloads_checkbox.setStyleSheet("""
            QCheckBox {
                color: #ffffff;
                font-size: 13px;
                font-weight: bold;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #2f3e50;
                background-color: #242f3d;
            }
            QCheckBox::indicator:checked {
                background-color: #2481cc;
                border-color: #2481cc;
            }
            QCheckBox::indicator:hover {
                border-color: #2481cc;
            }
        """)
        self.body_layout.addWidget(self.save_downloads_checkbox)

        save_hint_label = QLabel(
            "در صورت غیرفعال بودن، آهنگ‌ها کاملاً آنلاین و مستقیم پخش شده و هیچ فایلی در کش یا حافظه دستگاه ذخیره نمی‌شود "
            "(در صورت وجود قبلی در پوشه دانلودها، از حافظه پخش خواهد شد)."
        )
        save_hint_label.setStyleSheet("color: #7f91a4; font-size: 11px; margin-bottom: 4px;")
        save_hint_label.setWordWrap(True)
        self.body_layout.addWidget(save_hint_label)

        path_label = QLabel(str(self._cache._config.downloads_dir))
        path_label.setStyleSheet("color: #7f91a4; font-size: 11px;")
        path_label.setWordWrap(True)
        path_label.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.body_layout.addWidget(path_label)

        btn_open_folder = QPushButton("📁 باز کردن پوشه TMusicDownloads")
        btn_open_folder.setStyleSheet("background-color: #242f3d; border: 1px solid #2f3e50;")
        btn_open_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open_folder.clicked.connect(self._on_open_downloads_folder)
        self.body_layout.addWidget(btn_open_folder)

        storage_actions_row = QHBoxLayout()
        storage_actions_row.setSpacing(10)

        cache_info_layout = QVBoxLayout()
        cache_label = QLabel("حجم کش:")
        cache_label.setStyleSheet("font-size: 12px; color: #7f91a4;")

        max_size_str = self._cache.get_formatted_max_size()
        self.cache_size_val = QLabel(f"{self._cache.get_formatted_size()} / {max_size_str}")
        self.cache_size_val.setStyleSheet("font-size: 13px; font-weight: bold; color: #4fae4e;")

        cache_info_layout.addWidget(cache_label)
        cache_info_layout.addWidget(self.cache_size_val)

        downloads_info_layout = QVBoxLayout()
        downloads_label = QLabel("حجم دانلودها:")
        downloads_label.setStyleSheet("font-size: 12px; color: #7f91a4;")
        self.downloads_size_val = QLabel(self._cache.get_formatted_downloads_size())
        self.downloads_size_val.setStyleSheet("font-size: 13px; font-weight: bold; color: #6ab3f3;")
        downloads_info_layout.addWidget(downloads_label)
        downloads_info_layout.addWidget(self.downloads_size_val)

        btn_clear = QPushButton("🗑️ پاک‌سازی کش")
        btn_clear.setStyleSheet("background-color: #242f3d; color: #e53935; border: 1px solid #3b242d;")
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.clicked.connect(self._on_clear_cache)

        storage_actions_row.addLayout(cache_info_layout)
        storage_actions_row.addLayout(downloads_info_layout)
        storage_actions_row.addStretch()
        storage_actions_row.addWidget(btn_clear)
        self.body_layout.addLayout(storage_actions_row)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #242f3d; margin: 4px 0;")
        self.body_layout.addWidget(sep2)

        btn_logout = QPushButton("🚪 خروج از حساب کاربری تلگرام (Log Out)")
        btn_logout.setStyleSheet("background-color: #e53935; font-weight: bold; padding: 10px;")
        btn_logout.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_logout.clicked.connect(self._on_logout_clicked)
        self.body_layout.addWidget(btn_logout)

    def _on_save_proxy(self) -> None:
        ptype = self.proxy_type.currentText()
        server = self.proxy_server.text().strip() or "127.0.0.1"
        port_txt = self.proxy_port.text().strip()
        port = int(port_txt) if port_txt.isdigit() else 10808

        self._settings.set_proxy(ptype, server, port, enabled=True)
        self.proxy_saved.emit(ptype, server, port)

    def _on_toggle_save_to_downloads(self, checked: bool) -> None:
        self._settings.set_save_to_downloads(checked)

    def _on_open_downloads_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._cache._config.downloads_dir)))

    def _on_clear_cache(self) -> None:
        self._cache.clear_all()
        max_size_str = self._cache.get_formatted_max_size()
        self.cache_size_val.setText(f"{self._cache.get_formatted_size()} / {max_size_str}")
        self.downloads_size_val.setText(self._cache.get_formatted_downloads_size())
        self.cache_cleared.emit()

    def _on_logout_clicked(self) -> None:
        reply = QMessageBox.question(
            self,
            "خروج از حساب",
            "آیا مطمئن هستید؟ با خروج، نشست و کش‌ها پاک شده و برنامه بسته خواهد شد (آهنگ‌های دانلودشده در TMusicDownloads باقی می‌مانند).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.logout_requested.emit()
            self.accept()