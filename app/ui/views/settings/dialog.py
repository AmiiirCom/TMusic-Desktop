from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QMessageBox, QPushButton, QWidget

from app.cache.service import CacheManager
from app.config import AppConfig
from app.settings.models import ProxySettings
from app.settings.service import SettingsService
from app.ui.views.base_modal import BaseModalDialog
from app.ui.views.settings.proxy_section import ProxySettingsSection
from app.ui.views.settings.storage_section import StorageSettingsSection


class SettingsDialog(BaseModalDialog):
    """Modular Settings and Storage management dialog coordinating all setting sections."""

    cache_cleared = Signal()
    proxy_saved = Signal(object)
    logout_requested = Signal()

    def __init__(
        self,
        cache_manager: CacheManager,
        settings_service: SettingsService,
        config: AppConfig,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title=f"تنظیمات و حافظه {config.app_name}", parent=parent)
        self._cache = cache_manager
        self._settings = settings_service
        self._config = config
        self.card_frame.setFixedWidth(460)
        self._init_body()

    def _init_body(self) -> None:
        # 1. Proxy Configuration Section
        self.proxy_section = ProxySettingsSection(self._settings.preferences.proxy, self)
        self.proxy_section.proxy_saved.connect(self._on_proxy_saved)
        self.body_layout.addWidget(self.proxy_section)

        self._add_separator()

        # 2. Storage & Downloads Section
        self.storage_section = StorageSettingsSection(self._cache, self._settings, self)
        self.storage_section.cache_cleared.connect(self.cache_cleared.emit)
        self.body_layout.addWidget(self.storage_section)

        self._add_separator()

        # 3. Logout Button
        btn_logout = QPushButton("🚪 خروج از حساب کاربری تلگرام (Log Out)")
        btn_logout.setStyleSheet("background-color: #e53935; font-weight: bold; padding: 10px;")
        btn_logout.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_logout.clicked.connect(self._on_logout_clicked)
        self.body_layout.addWidget(btn_logout)

    def _add_separator(self) -> None:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #242f3d; margin: 4px 0;")
        self.body_layout.addWidget(sep)

    def _on_proxy_saved(self, settings: ProxySettings) -> None:
        self._settings.set_proxy_settings(settings)
        self.proxy_saved.emit(settings)

    def _on_logout_clicked(self) -> None:
        reply = QMessageBox.question(
            self,
            "خروج از حساب",
            "آیا مطمئن هستید؟ با خروج، نشست و کش‌ها پاک شده و برنامه بسته خواهد شد.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.logout_requested.emit()
            self.accept()