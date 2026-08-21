from pathlib import Path
import sys
from PIL import Image as PILImage
from PySide6.QtCore import QByteArray, QRectF
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

# Ensure root directory is importable
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.ui.utils.icons import SVG_ICONS


def generate_icons() -> None:
    app = QGuiApplication(sys.argv)
    icons_dir = ROOT_DIR / "resources" / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)

    svg_data = SVG_ICONS["app_logo"]
    renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))

    size = 512
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(0, 0, 0, 0))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()

    png_path = icons_dir / "app.png"
    ico_path = icons_dir / "app.ico"

    # 1. Save crisp 512x512 PNG directly via Qt
    image.save(str(png_path))

    # 2. Open generated PNG with Pillow and build standard multi-resolution Windows ICO (16px to 256px)
    with PILImage.open(png_path) as pil_image:
        icon_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        pil_image.save(str(ico_path), format="ICO", sizes=icon_sizes)

    print(f"✅ Generated official app icons from vector SVG successfully in:\n  - {png_path}\n  - {ico_path}")


if __name__ == "__main__":
    generate_icons()