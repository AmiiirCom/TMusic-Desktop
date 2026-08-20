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
    """Initialize and configure the Qt Application with global LTR layout & Theme."""
    app = QApplication(sys.argv)
    app.setApplicationName(config.app_name)
    app.setApplicationVersion(config.app_version)
    app.setOrganizationName(config.organization_name)
    app.setOrganizationDomain(config.organization_domain)

    # Set universal Left-to-Right layout direction
    app.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

    # Setup & register application fonts
    setup_application_fonts(app, config.resources_dir)

    # Apply global Telegram Desktop theme stylesheet & slim scrollbars
    app.setStyleSheet(ThemeManager.get_global_stylesheet())

    return app