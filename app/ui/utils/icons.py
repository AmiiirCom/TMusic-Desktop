from PySide6.QtCore import QByteArray, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# Valid W3C SVG vector icons with zero truncation errors
SVG_ICONS: dict[str, str] = {
    "app_logo": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">'
        '<defs>'
        '<linearGradient id="linear-gradient" x1="32" y1="992" x2="992" y2="32" gradientUnits="userSpaceOnUse">'
        '<stop offset="0%" stop-color="#1c92d2"/>'
        '<stop offset="100%" stop-color="#45a7dc"/>'
        '</linearGradient>'
        '</defs>'
        '<circle cx="512" cy="512" r="480" fill="url(#linear-gradient)"/>'
        '<path fill="#f3fbfe" fill-rule="evenodd" d="M505.778,704.934c0,28.5-17.08,54.456-41.759,73.458-24.046,18.988-55.687,30.392-83.518,30.392-17.724,0-34.175-5.7-45.556-15.2-12.021-9.5-18.987-23.421-18.987-39.884,0-25.959,17.714-51.932,41.76-70.92,24.046-19.635,54.413-32.3,79.719-32.3,22.153,0,41.129,3.169,52.521,13.926V176.2h15.82c1.263,22.79,5.059,54.456,32.271,79.151,31,27.22,59.473,54.457,79.09,79.152,25.939,32.3,44.282,72.814,44.282,113.973a234,234,0,0,1-8.855,62.688,153.346,153.346,0,0,1,16.45,70.289c0,44.328-13.284,81.057-31.641,111.448H627.257c13.284-20.265,29.105-68.382,27.845-98.786-1.276-33.558-3.8-53.18-25.309-79.783-24.676-30.388-88.588-62.054-124.015-86.752V704.934ZM644.97,454.818c-1.262-33.56-17.713-59.52-39.223-86.122-24.675-30.392-64.542-55.718-99.969-75.983,1.263,45.591,31,91.816,58.21,116.511,31,27.223,46.188,41.792,64.532,64.582a221.944,221.944,0,0,1,15.188,21.54C644.97,482.038,645.6,465.574,644.97,454.818Z"/>'
        '</svg>'
    ),
    "window_minimize": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<line x1="5" y1="12" x2="19" y2="12"></line></svg>'
    ),
    "window_maximize": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="4.5" y="4.5" width="15" height="15" rx="1.5"></rect></svg>'
    ),
    "window_restore": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M8 4.5h11a1.5 1.5 0 0 1 1.5 1.5v11"></path>'
        '<rect x="3.5" y="8" width="12.5" height="12.5" rx="1.5"></rect></svg>'
    ),
    "music": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M9 18V5l12-2v13"></path>'
        '<circle cx="6" cy="18" r="3"></circle>'
        '<circle cx="18" cy="16" r="3"></circle></svg>'
    ),
    "equalizer": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
        '<line x1="18" y1="20" x2="18" y2="10"></line>'
        '<line x1="12" y1="20" x2="12" y2="4"></line>'
        '<line x1="6" y1="20" x2="6" y2="14"></line></svg>'
    ),
    "play": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="{color}" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<polygon points="7.5 4.5 19.5 12 7.5 19.5 7.5 4.5"></polygon></svg>'
    ),
    "pause": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="{color}" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="6" y="4" width="4" height="16" rx="1.2"></rect>'
        '<rect x="14" y="4" width="4" height="16" rx="1.2"></rect></svg>'
    ),
    "next": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="{color}" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<polygon points="5 4.5 15.5 12 5 19.5 5 4.5"></polygon>'
        '<line x1="19" y1="5" x2="19" y2="19"></line></svg>'
    ),
    "previous": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="{color}" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<polygon points="19 19.5 8.5 12 19 4.5 19 19.5"></polygon>'
        '<line x1="5" y1="19" x2="5" y2="5"></line></svg>'
    ),
    "heart_outline": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>'
    ),
    "heart_filled": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="{color}" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>'
    ),
    "settings": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="3"></circle>'
        '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06'
        'a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09'
        'A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06'
        'a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09'
        'A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06'
        'a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09'
        'a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06'
        'a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09'
        'a1.65 1.65 0 0 0-1.51 1z"></path></svg>'
    ),
    "search": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="11" cy="11" r="8"></circle>'
        '<line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>'
    ),
    "volume": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>'
        '<path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path>'
        '<path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path></svg>'
    ),
    "lyrics": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>'
        '<polyline points="14 2 14 8 20 8"></polyline>'
        '<line x1="16" y1="13" x2="8" y2="13"></line>'
        '<line x1="16" y1="17" x2="8" y2="17"></line>'
        '<line x1="10" y1="9" x2="8" y2="9"></line></svg>'
    ),
    "info": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="10"></circle>'
        '<line x1="12" y1="16" x2="12" y2="12"></line>'
        '<line x1="12" y1="8" x2="12.01" y2="8"></line></svg>'
    ),
    "close": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<line x1="18" y1="6" x2="6" y2="18"></line>'
        '<line x1="6" y1="6" x2="18" y2="18"></line></svg>'
    ),
    "folder": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>'
    ),
    "trash": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="3 6 5 6 21 6"></polyline>'
        '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>'
    ),
    "logout": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>'
        '<polyline points="16 17 21 12 16 7"></polyline>'
        '<line x1="21" y1="12" x2="9" y2="12"></line></svg>'
    ),
    "copy": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>'
        '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>'
    ),
    "check": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="20 6 9 17 4 12"></polyline></svg>'
    ),
}


def render_svg_to_painter(
    painter: QPainter,
    icon_name: str,
    target_rect: QRectF | QRect,
    color: str = "#ffffff",
) -> None:
    """Render a vector SVG icon directly into an active QPainter within target_rect."""
    template = SVG_ICONS.get(icon_name)
    if not template:
        return
    svg_content = template.format(color=color)
    renderer = QSvgRenderer(QByteArray(svg_content.encode("utf-8")))
    renderer.render(painter, QRectF(target_rect))


def get_svg_pixmap(icon_name: str, color: str = "#8192a5", size: int = 24) -> QPixmap:
    """Render anti-aliased, high-DPI crisp SVG pixmap."""
    template = SVG_ICONS.get(icon_name)
    if not template:
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))
        return pixmap

    svg_content = template.format(color=color)
    renderer = QSvgRenderer(QByteArray(svg_content.encode("utf-8")))

    scale = 2
    render_size = size * scale
    pixmap = QPixmap(render_size, render_size)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()

    pixmap.setDevicePixelRatio(scale)
    return pixmap


def get_svg_icon(icon_name: str, color: str = "#8192a5", size: int = 24) -> QIcon:
    """Create a QIcon from the rendered SVG pixmap."""
    pixmap = get_svg_pixmap(icon_name, color=color, size=size)
    return QIcon(pixmap)


def get_app_logo_pixmap(size: int = 80) -> QPixmap:
    """Render the official vector TMusic application logo."""
    template = SVG_ICONS["app_logo"]
    renderer = QSvgRenderer(QByteArray(template.encode("utf-8")))

    scale = 2
    render_size = size * scale
    pixmap = QPixmap(render_size, render_size)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()

    pixmap.setDevicePixelRatio(scale)
    return pixmap

def get_application_icon() -> QIcon:
    """
    Generate a high-DPI multi-resolution QIcon (16px to 512px) from the official vector app_logo
    for Taskbar, Alt+Tab, and OS window decorations.
    """
    icon = QIcon()
    for size in (16, 20, 24, 32, 48, 64, 128, 256, 512):
        pixmap = get_app_logo_pixmap(size=size)
        icon.addPixmap(pixmap)
    return icon