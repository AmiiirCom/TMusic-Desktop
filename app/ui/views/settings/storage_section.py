from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.cache.service import CacheManager
from app.settings.service import SettingsService


class StorageSettingsSection(QWidget):
    """Encapsulated UI component managing Cache, Downloads directory, and Offline Playback."""

    cache_cleared = Signal()

    def __init__(self, cache_manager: CacheManager, settings_service: SettingsService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cache = cache_manager
        self._settings = settings_service
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title = QLabel("📂 مدیریت دانلود و ذخیره‌سازی")
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #6ab3f3;")
        layout.addWidget(title)

        self.save_checkbox = QCheckBox("ذخیره خودکار آهنگ‌ها در حافظه (پخش آفلاین)")
        self.save_checkbox.setChecked(self._settings.preferences.save_to_downloads)
        self.save_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_checkbox.toggled.connect(self._settings.set_save_to_downloads)
        layout.addWidget(self.save_checkbox)

        hint = QLabel("در صورت غیرفعال بودن، آهنگ‌ها کاملاً آنلاین پخش شده و کش دائمی ذخیره نمی‌شود.")
        hint.setStyleSheet("color: #7f91a4; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        btn_open = QPushButton("📁 باز کردن پوشه TMusicDownloads")
        btn_open.setStyleSheet("background-color: #242f3d; border: 1px solid #2f3e50;")
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._cache._config.downloads_dir))))
        layout.addWidget(btn_open)

        row = QHBoxLayout()
        self.cache_val = QLabel(f"{self._cache.get_formatted_size()} / {self._cache.get_formatted_max_size()}")
        self.cache_val.setStyleSheet("font-size: 13px; font-weight: bold; color: #4fae4e;")

        self.dl_val = QLabel(self._cache.get_formatted_downloads_size())
        self.dl_val.setStyleSheet("font-size: 13px; font-weight: bold; color: #6ab3f3;")

        btn_clear = QPushButton("🗑️ پاک‌سازی کش")
        btn_clear.setStyleSheet("background-color: #242f3d; color: #e53935; border: 1px solid #3b242d;")
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.clicked.connect(self._on_clear_cache)

        row.addWidget(QLabel("حجم کش:"))
        row.addWidget(self.cache_val)
        row.addSpacing(12)
        row.addWidget(QLabel("دانلودها:"))
        row.addWidget(self.dl_val)
        row.addStretch()
        row.addWidget(btn_clear)
        layout.addLayout(row)

    def _on_clear_cache(self) -> None:
        self._cache.clear_all()
        self.cache_val.setText(f"{self._cache.get_formatted_size()} / {self._cache.get_formatted_max_size()}")
        self.dl_val.setText(self._cache.get_formatted_downloads_size())
        self.cache_cleared.emit()