import sys
from pathlib import Path
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter


def generate_icons() -> None:
    app = QGuiApplication(sys.argv)
    icons_dir = Path(__file__).resolve().parent.parent / "resources" / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)

    size = 256
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(0, 0, 0, 0))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Draw Telegram-blue circular background
    painter.setBrush(QColor("#2481cc"))
    painter.setPen(QColor(0, 0, 0, 0))
    painter.drawEllipse(8, 8, size - 16, size - 16)

    # Draw White Musical Note emoji / glyph
    painter.setPen(QColor("#ffffff"))
    font = QFont("Segoe UI Emoji", 110, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(image.rect(), 0x0084, "🎵")
    painter.end()

    png_path = icons_dir / "app.png"
    ico_path = icons_dir / "app.ico"

    image.save(str(png_path), "PNG")
    image.save(str(ico_path), "ICO")

    print(f"Generated official app icons successfully in:\n  - {png_path}\n  - {ico_path}")


if __name__ == "__main__":
    generate_icons()