class ThemeManager:
    """Centralized Telegram Desktop Dark Theme styling and palette."""

    # Telegram Desktop Palette
    BG_DARK = "#0e1621"  # Main chat/list background
    BG_SIDEBAR = "#17212b"  # Sidebar, topbar, playerbar background
    BG_CARD = "#242f3d"  # Hover, input and card background
    BG_ACTIVE = "#2b5278"  # Active selection
    ACCENT_BLUE = "#2481cc"  # Telegram primary blue
    ACCENT_BLUE_HOVER = "#1d72b8"
    TEXT_PRIMARY = "#ffffff"
    TEXT_SECONDARY = "#7f91a4"
    TEXT_MUTED = "#5d6e80"
    BORDER_COLOR = "#0e1621"

    @classmethod
    def get_global_stylesheet(cls) -> str:
        """Master Qt stylesheet implementing Telegram Desktop aesthetic."""
        return f"""
        /* --- Base App Typography & Rendering --- */
        QWidget {{
            font-family: 'Vazirmatn', 'Segoe UI', 'Tahoma', 'Arial', sans-serif;
            color: {cls.TEXT_PRIMARY};
            font-size: 13px;
            selection-background-color: {cls.ACCENT_BLUE};
            selection-color: #ffffff;
        }}

        /* --- Telegram Desktop Slim Custom Scrollbars --- */
        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 6px;
            margin: 0;
            border-radius: 3px;
        }}
        QScrollBar::handle:vertical {{
            background: #2f3e50;
            min-height: 24px;
            border-radius: 3px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {cls.ACCENT_BLUE};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: transparent;
        }}

        QScrollBar:horizontal {{
            border: none;
            background: transparent;
            height: 6px;
            margin: 0;
            border-radius: 3px;
        }}
        QScrollBar::handle:horizontal {{
            background: #2f3e50;
            min-width: 24px;
            border-radius: 3px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {cls.ACCENT_BLUE};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: transparent;
        }}

        /* --- Tooltips --- */
        QToolTip {{
            background-color: {cls.BG_CARD};
            color: {cls.TEXT_PRIMARY};
            border: 1px solid #3b4e64;
            padding: 5px 8px;
            border-radius: 4px;
            font-size: 12px;
        }}

        /* --- Splitter --- */
        QSplitter::handle {{
            background-color: {cls.BORDER_COLOR};
        }}
        """