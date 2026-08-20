from typing import Any
from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QWindow
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from app.config import AppConfig
from app.ui.utils.icons import get_app_logo_pixmap, get_svg_icon


class CustomTitleBar(QWidget):
    """
    Sleek, responsive custom TitleBar modeled after Telegram Desktop.
    Supports native Windows Aero-Snap dragging, double-click maximize/restore,
    and vector window control buttons with subtle rounded corners.
    """

    minimize_requested = Signal()
    maximize_restore_requested = Signal()
    close_requested = Signal()

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._parent_window = parent
        self.setFixedHeight(36)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._is_maximized = False
        self._drag_start_pos: QPoint | None = None

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(8)

        # 1. Left Section: Vector Logo & Application Title
        self.app_icon = QLabel()
        self.app_icon.setFixedSize(18, 18)
        self.app_icon.setPixmap(get_app_logo_pixmap(size=18))

        self.title_label = QLabel(self._config.app_full_name)

        layout.addWidget(self.app_icon)
        layout.addWidget(self.title_label)
        layout.addStretch()

        # 2. Right Section: Window Controls
        self.btn_min = QPushButton()
        self.btn_min.setObjectName("btnTitleControl")
        self.btn_min.setIcon(get_svg_icon("window_minimize", "#8192a5", 14))
        self.btn_min.setIconSize(QSize(14, 14))
        self.btn_min.setToolTip(self.tr("Minimize"))
        self.btn_min.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_min.clicked.connect(self.minimize_requested.emit)

        self.btn_max = QPushButton()
        self.btn_max.setObjectName("btnTitleControl")
        self.btn_max.setIcon(get_svg_icon("window_maximize", "#8192a5", 13))
        self.btn_max.setIconSize(QSize(13, 13))
        self.btn_max.setToolTip(self.tr("Maximize"))
        self.btn_max.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_max.clicked.connect(self.maximize_restore_requested.emit)

        self.btn_close = QPushButton()
        self.btn_close.setObjectName("btnTitleClose")
        self.btn_close.setIcon(get_svg_icon("close", "#8192a5", 14))
        self.btn_close.setIconSize(QSize(14, 14))
        self.btn_close.setToolTip(self.tr("Close"))
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self.close_requested.emit)

        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(self.btn_close)

        self._apply_style(False)

    def _apply_style(self, is_max: bool) -> None:
        radius = "0px" if is_max else "10px"
        self.setStyleSheet(f"""
            CustomTitleBar {{
                background-color: #17212b;
                border-top-left-radius: {radius};
                border-top-right-radius: {radius};
                border-bottom: 1px solid #0e1621;
            }}
            QLabel {{
                background: transparent;
                color: #8192a5;
                font-family: 'Segoe UI', 'Vazirmatn', sans-serif;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton#btnTitleControl {{
                background-color: transparent;
                border: none;
                min-width: 44px;
                max-width: 44px;
                min-height: 35px;
                max-height: 35px;
                padding: 0px;
            }}
            QPushButton#btnTitleControl:hover {{
                background-color: rgba(255, 255, 255, 0.08);
            }}
            QPushButton#btnTitleControl:pressed {{
                background-color: rgba(255, 255, 255, 0.16);
            }}
            QPushButton#btnTitleClose {{
                background-color: transparent;
                border: none;
                border-top-right-radius: {radius};
                min-width: 44px;
                max-width: 44px;
                min-height: 35px;
                max-height: 35px;
                padding: 0px;
            }}
            QPushButton#btnTitleClose:hover {{
                background-color: #e53935;
            }}
            QPushButton#btnTitleClose:pressed {{
                background-color: #c62828;
            }}
        """)

    def set_maximized(self, is_max: bool) -> None:
        """Update window state icon and border radius dynamically."""
        self._is_maximized = is_max
        self._apply_style(is_max)
        if is_max:
            self.btn_max.setIcon(get_svg_icon("window_restore", "#8192a5", 13))
            self.btn_max.setToolTip(self.tr("Restore"))
        else:
            self.btn_max.setIcon(get_svg_icon("window_maximize", "#8192a5", 13))
            self.btn_max.setToolTip(self.tr("Maximize"))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            win = self.window()
            if win.windowHandle():
                win.windowHandle().startSystemMove()
            else:
                self._drag_start_pos = event.globalPosition().toPoint() - win.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start_pos and (event.buttons() & Qt.MouseButton.LeftButton):
            win = self.window()
            if self._is_maximized:
                self.maximize_restore_requested.emit()
                self._drag_start_pos = QPoint(int(win.width() / 2), 18)
            win.move(event.globalPosition().toPoint() - self._drag_start_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximize_restore_requested.emit()
        super().mouseDoubleClickEvent(event)