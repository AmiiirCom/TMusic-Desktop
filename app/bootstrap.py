import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.config import AppConfig
from app.core.fonts import setup_application_fonts
from app.ui.themes.theme_manager import ThemeManager
from app.core.security import CryptoManager
from app.cache.service import CacheManager
from app.telegram.adapter import TDLibAdapter

def create_application(config: AppConfig) -> QApplication:
    """Initialize and configure the Qt Application with Vazirmatn Font & Theme."""
    app = QApplication(sys.argv)
    app.setApplicationName(config.app_name)
    app.setApplicationVersion(config.app_version)
    app.setOrganizationName(config.organization_name)
    app.setOrganizationDomain(config.organization_domain)

    # Set default RTL layout for Persian
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

    # Setup & register Vazirmatn Persian fonts
    setup_application_fonts(app, config.resources_dir)

    # Apply global Telegram Desktop theme stylesheet & slim scrollbars
    app.setStyleSheet(ThemeManager.get_global_stylesheet())

    return app