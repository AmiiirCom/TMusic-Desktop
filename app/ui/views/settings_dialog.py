from pathlib import Path
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
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
        self.card_frame.setFixedWidth(480)
        self._init_body()

    def _init_body(self) -> None:
        # ----- Proxy Section -----
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

        # Separator
        self._add_separator()

        # ----- Download Settings Section -----
        dl_title = QLabel("💾 تنظیمات ذخیره‌سازی آهنگ‌ها")
        dl_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #6ab3f3;")
        self.body_layout.addWidget(dl_title)

        # Checkbox: Enable saving
        self.save_check = QCheckBox("ذخیره خودکار آهنگ‌های دانلود شده در دیسک")
        self.save_check.setChecked(self._settings.save_tracks_enabled)
        self.save_check.stateChanged.connect(self._on_save_toggle)
        self.body_layout.addWidget(self.save_check)

        # Path selector
        path_layout = QHBoxLayout()
        path_layout.setSpacing(8)

        self.dl_path_edit = QLineEdit()
        self.dl_path_edit.setReadOnly(True)
        self.dl_path_edit.setText(str(self._settings.effective_downloads_dir))
        self.dl_path_edit.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.dl_path_edit.setStyleSheet("background-color: #242f3d; color: #c0d0e0;")

        btn_choose = QPushButton("📂 انتخاب")
        btn_choose.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_choose.clicked.connect(self._on_choose_directory)

        path_layout.addWidget(self.dl_path_edit, stretch=1)
        path_layout.addWidget(btn_choose)
        self.body_layout.addLayout(path_layout)

        # Separator
        self._add_separator()

        # ----- Storage Info Section -----
        storage_title = QLabel("📂 حجم دانلودها و کش")
        storage_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #6ab3f3;")
        self.body_layout.addWidget(storage_title)

        # Current downloads folder display (clickable)
        path_label = QLabel(str(self._settings.effective_downloads_dir))
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
        # Use effective downloads dir for size
        self.downloads_size_val = QLabel(self._cache.get_formatted_downloads_size(self._settings.effective_downloads_dir))
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

        # Separator
        self._add_separator()

        # ----- Logout Button -----
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

    def _on_save_proxy(self) -> None:
        ptype = self.proxy_type.currentText()
        server = self.proxy_server.text().strip() or "127.0.0.1"
        port_txt = self.proxy_port.text().strip()
        port = int(port_txt) if port_txt.isdigit() else 10808

        self._settings.set_proxy(ptype, server, port, enabled=True)
        self.proxy_saved.emit(ptype, server, port)

    def _on_open_downloads_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._settings.effective_downloads_dir)))

    def _on_clear_cache(self) -> None:
        self._cache.clear_all()
        max_size_str = self._cache.get_formatted_max_size()
        self.cache_size_val.setText(f"{self._cache.get_formatted_size()} / {max_size_str}")
        self.downloads_size_val.setText(self._cache.get_formatted_downloads_size(self._settings.effective_downloads_dir))
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

    def _on_save_toggle(self, state: int) -> None:
        enabled = state == Qt.CheckState.Checked
        self._settings.set_save_tracks_enabled(enabled)

    def _on_choose_directory(self) -> None:
        """Open directory picker and update the setting if a folder is selected."""
        current = str(self._settings.effective_downloads_dir)
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "انتخاب پوشه برای ذخیره آهنگ‌ها",
            current,
            QFileDialog.Option.ShowDirsOnly,
        )
        if dir_path:
            path = Path(dir_path)
            self._settings.set_downloads_dir(path)
            self.dl_path_edit.setText(str(path))
            # Update the displayed size
            self.downloads_size_val.setText(
                self._cache.get_formatted_downloads_size(self._settings.effective_downloads_dir)
            )