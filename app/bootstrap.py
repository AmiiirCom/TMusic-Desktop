import ctypes
import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.config import AppConfig
from app.core.fonts import setup_application_fonts
from app.ui.themes.theme_manager import ThemeManager
from app.ui.utils.icons import get_application_icon


def create_application(config: AppConfig) -> QApplication:
    """Initialize and configure the Qt Application with global Taskbar icon & Windows AppUserModelID."""
    # 1. On Windows, explicitly decouple process from python.exe so Taskbar displays dedicated app icon
    if sys.platform == "win32":
        try:
            app_id = f"{config.organization_name}.{config.app_name}.{config.app_version}"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(config.app_name)
    app.setApplicationVersion(config.app_version)
    app.setOrganizationName(config.organization_name)
    app.setOrganizationDomain(config.organization_domain)

    # 2. Set global high-DPI application & taskbar icon across all windows
    app_icon = get_application_icon()
    app.setWindowIcon(app_icon)

    # Set universal Left-to-Right layout direction
    app.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

    # Setup & register application fonts
    setup_application_fonts(app, config.resources_dir)

    # Apply global Telegram Desktop theme stylesheet & slim scrollbars
    app.setStyleSheet(ThemeManager.get_global_stylesheet())

    return app