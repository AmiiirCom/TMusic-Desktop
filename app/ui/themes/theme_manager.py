class ThemeManager:
    """Centralized Telegram Desktop Dark Theme styling, color palette, and interactive micro-effects."""

    # Telegram Desktop Dark Palette
    BG_DARK = "#0e1621"        # Main background
    BG_SIDEBAR = "#17212b"     # Sidebar and playerbar surface
    BG_CARD = "#242f3d"        # Cards, inputs, and unhovered surfaces
    BG_CARD_HOVER = "#2b3848"  # Card hover surface
    BG_ACTIVE = "#2b5278"      # Active selection
    ACCENT_BLUE = "#2481cc"    # Primary Telegram blue
    ACCENT_BLUE_HOVER = "#1d72b8"
    ACCENT_BLUE_PRESSED = "#175d96"
    BORDER_COLOR = "#2f3e50"
    BORDER_HOVER = "#3f546c"
    TEXT_PRIMARY = "#ffffff"
    TEXT_SECONDARY = "#7f91a4"
    TEXT_MUTED = "#5d6e80"

    @classmethod
    def get_global_stylesheet(cls) -> str:
        """
        Master Qt stylesheet implementing reactive, zero-lag Telegram Desktop interactive design.
        Enforces transparent background for all QLabels globally.
        """
        return f"""
        /* --- Base Typography & Palette --- */
        QWidget {{
            color: {cls.TEXT_PRIMARY};
            selection-background-color: {cls.ACCENT_BLUE};
            selection-color: #ffffff;
        }}

        /* --- Enforce 100% Transparent Backgrounds on all Labels --- */
        QLabel {{
            background: transparent;
            background-color: transparent;
            border: none;
        }}

        /* --- Push Buttons Interactive Motion --- */
        QPushButton {{
            background-color: {cls.BG_CARD};
            color: {cls.TEXT_PRIMARY};
            border: 1px solid {cls.BORDER_COLOR};
            border-radius: 8px;
            padding: 6px 14px;
            font-size: 13px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: {cls.BG_CARD_HOVER};
            border-color: {cls.BORDER_HOVER};
            color: #ffffff;
        }}
        QPushButton:pressed {{
            background-color: #1e2834;
            border-color: {cls.ACCENT_BLUE};
            padding-top: 7px;
            padding-bottom: 5px;
        }}
        QPushButton:disabled {{
            background-color: transparent;
            border-color: transparent;
            color: #4a5768;
        }}

        /* --- Text Inputs Hover & Focus Ring --- */
        QLineEdit {{
            background-color: {cls.BG_CARD};
            border: 1.5px solid {cls.BORDER_COLOR};
            border-radius: 8px;
            padding: 8px 12px;
            color: #ffffff;
            font-size: 13px;
        }}
        QLineEdit:hover {{
            border-color: {cls.BORDER_HOVER};
            background-color: #263342;
        }}
        QLineEdit:focus {{
            border-color: {cls.ACCENT_BLUE};
            background-color: #1c2734;
        }}

        /* --- ComboBox Hover & Active Dropdown --- */
        QComboBox {{
            background-color: {cls.BG_CARD};
            border: 1.5px solid {cls.BORDER_COLOR};
            border-radius: 8px;
            padding: 7px 12px;
            color: #ffffff;
            font-size: 13px;
            min-height: 20px;
        }}
        QComboBox:hover {{
            background-color: {cls.BG_CARD_HOVER};
            border-color: {cls.BORDER_HOVER};
        }}
        QComboBox:focus, QComboBox:on {{
            border-color: {cls.ACCENT_BLUE};
            background-color: #1c2734;
        }}
        QComboBox::drop-down {{
            border: none;
            width: 24px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {cls.BG_SIDEBAR};
            color: #ffffff;
            border: 1px solid {cls.BORDER_COLOR};
            border-radius: 8px;
            padding: 4px;
            selection-background-color: {cls.ACCENT_BLUE};
            outline: none;
        }}

        /* --- CheckBox Interactive Indicator --- */
        QCheckBox {{
            color: #ffffff;
            font-size: 13px;
            font-weight: 500;
            spacing: 10px;
            background: transparent;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border-radius: 5px;
            border: 1.5px solid {cls.BORDER_COLOR};
            background-color: {cls.BG_CARD};
        }}
        QCheckBox::indicator:hover {{
            border-color: {cls.ACCENT_BLUE};
            background-color: {cls.BG_CARD_HOVER};
        }}
        QCheckBox::indicator:checked {{
            background-color: {cls.ACCENT_BLUE};
            border-color: {cls.ACCENT_BLUE};
        }}
        QCheckBox::indicator:checked:hover {{
            background-color: {cls.ACCENT_BLUE_HOVER};
            border-color: {cls.ACCENT_BLUE_HOVER};
        }}

        /* --- Sliders with Expanding Hover Handle --- */
        QSlider::groove:horizontal {{
            height: 4px;
            background: {cls.BG_CARD};
            border-radius: 2px;
        }}
        QSlider::sub-page:horizontal {{
            background: {cls.ACCENT_BLUE};
            border-radius: 2px;
        }}
        QSlider::sub-page:horizontal:hover {{
            background: #4098e0;
        }}
        QSlider::handle:horizontal {{
            background: #ffffff;
            width: 10px;
            height: 10px;
            margin: -3px 0;
            border-radius: 5px;
        }}
        QSlider::handle:horizontal:hover {{
            background: #ffffff;
            width: 14px;
            height: 14px;
            margin: -5px 0;
            border-radius: 7px;
        }}
        QSlider::handle:horizontal:pressed {{
            background: #6ab3f3;
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
            border-radius: 6px;
            font-size: 12px;
        }}

        /* --- Splitter --- */
        QSplitter::handle {{
            background-color: {cls.BORDER_COLOR};
        }}
        """