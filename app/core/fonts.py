import logging
from pathlib import Path
import urllib.request
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

logger = logging.getLogger("tmusic.fonts")

VAZIRMATN_REGULAR_URL = "https://raw.githubusercontent.com/rastikerdar/vazirmatn/master/fonts/ttf/Vazirmatn-Regular.ttf"
VAZIRMATN_BOLD_URL = "https://raw.githubusercontent.com/rastikerdar/vazirmatn/master/fonts/ttf/Vazirmatn-Bold.ttf"


def setup_application_fonts(app: QApplication, resources_dir: Path) -> None:
    """Download (if missing) and register Vazirmatn Persian fonts into Qt with valid point size."""
    fonts_dir = resources_dir / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)

    font_targets = [
        (fonts_dir / "Vazirmatn-Regular.ttf", VAZIRMATN_REGULAR_URL),
        (fonts_dir / "Vazirmatn-Bold.ttf", VAZIRMATN_BOLD_URL),
    ]

    for font_file, url in font_targets:
        if not font_file.exists():
            try:
                logger.debug("Downloading Persian font %s...", font_file.name)
                urllib.request.urlretrieve(url, str(font_file))
                logger.debug("Font %s downloaded successfully.", font_file.name)
            except Exception as exc:
                logger.warning("Could not auto-download font %s: %s", font_file.name, exc)

    # Register all TTF fonts in directory
    for font_path in fonts_dir.glob("*.ttf"):
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            logger.debug("Registered font family: %s", families)

    # Apply Vazirmatn / Segoe UI as the default Qt Application font with valid positive point size (10pt)
    app_font = QFont("Segoe UI")
    app_font.setPointSize(10)
    app_font.setFamilies(["Vazirmatn", "Segoe UI", "Tahoma", "Arial"])
    app_font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(app_font)