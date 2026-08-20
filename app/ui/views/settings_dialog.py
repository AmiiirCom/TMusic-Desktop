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
from app.settings.service import ProxySettings, SettingsService, detect_system_proxy
from app.ui.views.base_modal import BaseModalDialog


class SettingsDialog(BaseModalDialog):
    """Clean, well-proportioned Settings, Proxy, and Storage management modal."""

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
        title = f"{config.app_name} Settings and Storage"
        super().__init__(title=title, parent=parent)
        self._cache = cache_manager
        self._settings = settings_service
        self._config = config
        self.card_frame.setFixedWidth(460)
        self._init_body()

    def _init_body(self) -> None:
        # Proxy Section
        proxy_title = QLabel(self.tr("Telegram Proxy Settings"))
        proxy_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #6ab3f3;")
        self.body_layout.addWidget(proxy_title)

        # Mode Selection
        self.proxy_mode_combo = QComboBox()
        self.proxy_mode_combo.addItem(self.tr("Direct Connection"), "DIRECT")
        self.proxy_mode_combo.addItem(self.tr("System Proxy"), "SYSTEM")
        self.proxy_mode_combo.addItem(self.tr("Custom Proxy"), "CUSTOM")

        current_mode = self._settings.preferences.proxy.mode
        idx = self.proxy_mode_combo.findData(current_mode)
        if idx != -1:
            self.proxy_mode_combo.setCurrentIndex(idx)
        else:
            self.proxy_mode_combo.setCurrentIndex(0)

        self.proxy_mode_combo.currentIndexChanged.connect(self._on_proxy_mode_changed)
        self.body_layout.addWidget(self.proxy_mode_combo)

        # Status Hint
        self.proxy_status_hint = QLabel()
        self.proxy_status_hint.setWordWrap(True)
        self.proxy_status_hint.setStyleSheet("font-size: 11px; color: #7f91a4; margin: 2px 0;")
        self.body_layout.addWidget(self.proxy_status_hint)

        # Manual Form Frame
        self.manual_proxy_frame = QFrame()
        form = QFormLayout(self.manual_proxy_frame)
        form.setContentsMargins(0, 4, 0, 4)
        form.setSpacing(8)

        self.proxy_type = QComboBox()
        self.proxy_type.addItems(["SOCKS5", "HTTP"])
        self.proxy_type.setCurrentText(self._settings.preferences.proxy.proxy_type)

        self.proxy_server = QLineEdit()
        self.proxy_server.setText(self._settings.preferences.proxy.server)

        self.proxy_port = QLineEdit()
        self.proxy_port.setText(str(self._settings.preferences.proxy.port))

        form.addRow(self.tr("Protocol:"), self.proxy_type)
        form.addRow(self.tr("Server:"), self.proxy_server)
        form.addRow(self.tr("Port:"), self.proxy_port)
        self.body_layout.addWidget(self.manual_proxy_frame)

        btn_save_proxy = QPushButton(self.tr("Save Proxy Settings"))
        btn_save_proxy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save_proxy.clicked.connect(self._on_save_proxy)
        self.body_layout.addWidget(btn_save_proxy)

        self._on_proxy_mode_changed()

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("color: #242f3d; margin: 4px 0;")
        self.body_layout.addWidget(sep1)

        # Storage & Download Settings
        storage_title = QLabel(self.tr("Storage and Downloads"))
        storage_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #6ab3f3;")
        self.body_layout.addWidget(storage_title)

        self.save_downloads_checkbox = QCheckBox(self.tr("Save tracks to storage for offline playback"))
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
            self.tr("When disabled, tracks stream online directly without persistent local file caching.")
        )
        save_hint_label.setStyleSheet("color: #7f91a4; font-size: 11px; margin-bottom: 4px;")
        save_hint_label.setWordWrap(True)
        self.body_layout.addWidget(save_hint_label)

        path_label = QLabel(str(self._cache._config.downloads_dir))
        path_label.setStyleSheet("color: #7f91a4; font-size: 11px;")
        path_label.setWordWrap(True)
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.body_layout.addWidget(path_label)

        btn_open_folder = QPushButton(self.tr("Open Downloads Folder"))
        btn_open_folder.setStyleSheet("background-color: #242f3d; border: 1px solid #2f3e50;")
        btn_open_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open_folder.clicked.connect(self._on_open_downloads_folder)
        self.body_layout.addWidget(btn_open_folder)

        storage_actions_row = QHBoxLayout()
        storage_actions_row.setSpacing(10)

        cache_info_layout = QVBoxLayout()
        cache_label = QLabel(self.tr("Cache Size:"))
        cache_label.setStyleSheet("font-size: 12px; color: #7f91a4;")

        max_size_str = self._cache.get_formatted_max_size()
        self.cache_size_val = QLabel(f"{self._cache.get_formatted_size()} / {max_size_str}")
        self.cache_size_val.setStyleSheet("font-size: 13px; font-weight: bold; color: #4fae4e;")

        cache_info_layout.addWidget(cache_label)
        cache_info_layout.addWidget(self.cache_size_val)

        downloads_info_layout = QVBoxLayout()
        downloads_label = QLabel(self.tr("Downloads:"))
        downloads_label.setStyleSheet("font-size: 12px; color: #7f91a4;")
        self.downloads_size_val = QLabel(self._cache.get_formatted_downloads_size())
        self.downloads_size_val.setStyleSheet("font-size: 13px; font-weight: bold; color: #6ab3f3;")
        downloads_info_layout.addWidget(downloads_label)
        downloads_info_layout.addWidget(self.downloads_size_val)

        btn_clear = QPushButton(self.tr("Clear Cache"))
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

        btn_logout = QPushButton(self.tr("Log Out of Telegram"))
        btn_logout.setStyleSheet("background-color: #e53935; font-weight: bold; padding: 10px;")
        btn_logout.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_logout.clicked.connect(self._on_logout_clicked)
        self.body_layout.addWidget(btn_logout)

    def _on_proxy_mode_changed(self) -> None:
        mode = self.proxy_mode_combo.currentData()
        if mode == "DIRECT":
            self.manual_proxy_frame.hide()
            self.proxy_status_hint.setText(self.tr("Connecting directly without proxy."))
            self.proxy_status_hint.setStyleSheet("color: #7f91a4; font-size: 11px;")
        elif mode == "SYSTEM":
            self.manual_proxy_frame.hide()
            sys_proxy = detect_system_proxy()
            if sys_proxy:
                ptype, host, port, _, _ = sys_proxy
                self.proxy_status_hint.setText(f"{self.tr('System proxy detected:')} {ptype}://{host}:{port}")
                self.proxy_status_hint.setStyleSheet("color: #4fae4e; font-size: 11px; font-weight: bold;")
            else:
                self.proxy_status_hint.setText(self.tr("No active system proxy detected."))
                self.proxy_status_hint.setStyleSheet("color: #e6a23c; font-size: 11px;")
        elif mode == "CUSTOM":
            self.manual_proxy_frame.show()
            self.proxy_status_hint.setText(self.tr("Enter SOCKS5 or HTTP proxy parameters:"))
            self.proxy_status_hint.setStyleSheet("color: #6ab3f3; font-size: 11px;")

    def _on_save_proxy(self) -> None:
        mode = self.proxy_mode_combo.currentData()
        ptype = self.proxy_type.currentText()
        server = self.proxy_server.text().strip() or "127.0.0.1"
        port_txt = self.proxy_port.text().strip()
        port = int(port_txt) if port_txt.isdigit() else 10808

        settings = ProxySettings(
            mode=mode,
            enabled=(mode != "DIRECT"),
            proxy_type=ptype,
            server=server,
            port=port,
        )

        self._settings.set_proxy_settings(settings)
        self.proxy_saved.emit(settings)

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
            self.tr("Log Out"),
            self.tr("Are you sure you want to log out? Local cache and session data will be cleared."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.logout_requested.emit()
            self.accept()