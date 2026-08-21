from pathlib import Path
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap

from app.models.chat import FAVORITES_CHAT_ID
from app.ui.utils.icons import render_svg_to_painter

TELEGRAM_AVATAR_PALETTE: tuple[str, ...] = (
    "#e17076",
    "#faa774",
    "#a695e7",
    "#7bc862",
    "#6ec9cb",
    "#65aadd",
    "#ee7aae",
    "#f28935",
    "#56b949",
    "#8e55e7",
)


def get_chat_avatar_color(chat_id: int) -> str:
    if chat_id == FAVORITES_CHAT_ID:
        return "#e53935"
    idx = abs(chat_id) % len(TELEGRAM_AVATAR_PALETTE)
    return TELEGRAM_AVATAR_PALETTE[idx]


def create_chat_avatar_pixmap(title: str, chat_id: int, size: int = 42) -> QPixmap:
    scale = 2
    render_size = size * scale
    pixmap = QPixmap(render_size, render_size)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    path = QPainterPath()
    path.addEllipse(0, 0, render_size, render_size)
    painter.setClipPath(path)

    bg_color = QColor(get_chat_avatar_color(chat_id))
    painter.fillRect(0, 0, render_size, render_size, bg_color)

    if chat_id == FAVORITES_CHAT_ID:
        icon_dim = render_size * 0.50
        ix = (render_size - icon_dim) / 2.0
        iy = (render_size - icon_dim) / 2.0
        render_svg_to_painter(painter, "heart_filled", QRectF(ix, iy, icon_dim, icon_dim), color="#ffffff")
    else:
        letter = title.strip()[:1].upper() if title.strip() else "C"
        painter.setPen(QColor("#ffffff"))
        font = QFont("Segoe UI")
        font.setPointSize(max(1, int(16 * scale)))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, letter)

    painter.end()
    pixmap.setDevicePixelRatio(scale)
    return pixmap


def create_circular_avatar_pixmap(
    photo_path: str | None,
    minithumb_data: bytes | None,
    initial: str,
    size: int = 42,
) -> QPixmap:
    scale = 2
    render_size = size * scale
    pixmap = QPixmap(render_size, render_size)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    path = QPainterPath()
    path.addEllipse(2, 2, render_size - 4, render_size - 4)
    painter.setClipPath(path)

    has_drawn = False

    if photo_path and Path(photo_path).exists():
        src = QPixmap(str(photo_path))
        if not src.isNull():
            scaled = src.scaled(
                render_size,
                render_size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - render_size) // 2
            y = (scaled.height() - render_size) // 2
            painter.drawPixmap(0, 0, scaled.copy(x, y, render_size, render_size))
            has_drawn = True

    if not has_drawn and minithumb_data:
        src = QPixmap()
        if src.loadFromData(minithumb_data):
            scaled = src.scaled(
                render_size,
                render_size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - render_size) // 2
            y = (scaled.height() - render_size) // 2
            painter.drawPixmap(0, 0, scaled.copy(x, y, render_size, render_size))
            has_drawn = True

    if not has_drawn:
        painter.fillRect(0, 0, render_size, render_size, QColor("#2b5278"))
        painter.setPen(QColor("#ffffff"))
        font = QFont("Segoe UI")
        font.setPointSize(max(1, int(15 * scale)))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, initial)

    painter.setClipping(False)
    painter.setPen(QPen(QColor("#3b5068"), 1.5 * scale))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(2, 2, render_size - 4, render_size - 4)

    painter.end()
    pixmap.setDevicePixelRatio(scale)
    return pixmap


def create_rounded_cover_pixmap(
    minithumb_data: bytes | None = None,
    cover_path: str | None = None,
    size: int = 44,
    is_active: bool = False,
) -> QPixmap:
    scale = 2
    render_size = size * scale
    target_pixmap = QPixmap(render_size, render_size)
    target_pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(target_pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    path = QPainterPath()
    path.addRoundedRect(0, 0, render_size, render_size, 8 * scale, 8 * scale)
    painter.setClipPath(path)

    has_drawn = False

    if cover_path and Path(cover_path).exists():
        src = QPixmap(str(cover_path))
        if not src.isNull():
            scaled = src.scaled(
                render_size,
                render_size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - render_size) // 2
            y = (scaled.height() - render_size) // 2
            painter.drawPixmap(0, 0, scaled.copy(x, y, render_size, render_size))
            has_drawn = True

    if not has_drawn and minithumb_data:
        src = QPixmap()
        if src.loadFromData(minithumb_data):
            scaled = src.scaled(
                render_size,
                render_size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - render_size) // 2
            y = (scaled.height() - render_size) // 2
            painter.drawPixmap(0, 0, scaled.copy(x, y, render_size, render_size))
            has_drawn = True

    if not has_drawn:
        bg_color = QColor("#2481cc" if is_active else "#28384b")
        painter.fillRect(0, 0, render_size, render_size, bg_color)
        icon_dim = render_size * 0.48
        ix = (render_size - icon_dim) / 2.0
        iy = (render_size - icon_dim) / 2.0
        render_svg_to_painter(painter, "music", QRectF(ix, iy, icon_dim, icon_dim), color="#ffffff")

    if is_active:
        badge_size = 18 * scale
        badge_x = render_size - badge_size - (3 * scale)
        badge_y = render_size - badge_size - (3 * scale)

        painter.setClipping(False)
        painter.setBrush(QColor(79, 174, 78, 235))
        painter.setPen(QPen(QColor("#ffffff"), 1.2 * scale))
        painter.drawEllipse(badge_x, badge_y, badge_size, badge_size)

        eq_dim = badge_size * 0.55
        ex = badge_x + (badge_size - eq_dim) / 2.0
        ey = badge_y + (badge_size - eq_dim) / 2.0
        render_svg_to_painter(painter, "equalizer", QRectF(ex, ey, eq_dim, eq_dim), color="#ffffff")

    painter.end()
    target_pixmap.setDevicePixelRatio(scale)
    return target_pixmap


def create_connection_shield_pixmap(status: str = "ready", is_proxy: bool = False) -> QPixmap:
    scale = 2
    size = 20 * scale
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    shield_path = QPainterPath()
    shield_path.moveTo(size / 2, 2 * scale)
    shield_path.lineTo(size - (3 * scale), 5 * scale)
    shield_path.lineTo(size - (3 * scale), size * 0.55)
    shield_path.cubicTo(
        size - (3 * scale), size * 0.8,
        size / 2, size - (2 * scale),
        size / 2, size - (2 * scale),
    )
    shield_path.cubicTo(
        size / 2, size - (2 * scale),
        3 * scale, size * 0.8,
        3 * scale, size * 0.55,
    )
    shield_path.lineTo(3 * scale, 5 * scale)
    shield_path.closeSubpath()

    if status == "ready":
        fill_color = QColor("#2481cc" if is_proxy else "#4fae4e")
        border_color = QColor(255, 255, 255, 180)
        badge_symbol = "✓" if is_proxy else "•"
    else:
        fill_color = QColor("#242f3d")
        border_color = QColor("#5d6e80")
        badge_symbol = "⋯"

    painter.setBrush(fill_color)
    painter.setPen(QPen(border_color, 1 * scale))
    painter.drawPath(shield_path)

    painter.setPen(QColor("#ffffff" if status == "ready" else "#7f91a4"))
    font = QFont("Segoe UI")
    font.setPointSize(max(1, int(8 * scale)))
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, badge_symbol)

    painter.end()
    pixmap.setDevicePixelRatio(scale)
    return pixmap