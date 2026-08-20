from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.utils.icons import get_svg_icon
from app.ui.views.base_modal import BaseModalDialog


class LyricsDialog(BaseModalDialog):
    """Frameless unified modal displaying song lyrics with SVG copy action."""

    def __init__(self, title: str, artist: str, lyrics: str, parent: QWidget | None = None) -> None:
        super().__init__(title="Lyrics", parent=parent)
        self._lyrics = lyrics
        self.card_frame.setFixedSize(480, 540)
        self._init_body(title, artist)

    def _init_body(self, title: str, artist: str) -> None:
        header_layout = QVBoxLayout()
        header_layout.setSpacing(2)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #6ab3f3;")

        artist_lbl = QLabel(artist)
        artist_lbl.setStyleSheet("font-size: 12px; color: #7f91a4;")

        header_layout.addWidget(title_lbl)
        header_layout.addWidget(artist_lbl)
        self.body_layout.addLayout(header_layout)

        # Lyrics Text Box
        self.text_box = QTextEdit()
        self.text_box.setReadOnly(True)
        self.text_box.setPlainText(self._lyrics)
        self.text_box.setStyleSheet("""
            QTextEdit {
                background-color: #0e1621;
                border: 1px solid #242f3d;
                border-radius: 8px;
                color: #e4ecf2;
                font-family: 'Segoe UI', 'Vazirmatn', sans-serif;
                font-size: 14px;
                line-height: 1.8;
                padding: 14px;
                selection-background-color: #2481cc;
            }
        """)
        self.body_layout.addWidget(self.text_box)

        # Action Button
        btn_layout = QHBoxLayout()
        self.btn_copy = QPushButton(self.tr("Copy Lyrics"))
        self.btn_copy.setIcon(get_svg_icon("copy", "#6ab3f3", 16))
        self.btn_copy.setIconSize(QSize(16, 16))
        self.btn_copy.setStyleSheet("background-color: #242f3d; color: #6ab3f3; border: 1px solid #2f3e50;")
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.clicked.connect(self._on_copy_lyrics)

        btn_layout.addWidget(self.btn_copy)
        btn_layout.addStretch()
        self.body_layout.addLayout(btn_layout)

    def _on_copy_lyrics(self) -> None:
        QApplication.clipboard().setText(self._lyrics)
        self.btn_copy.setText(self.tr("Copied"))
        self.btn_copy.setIcon(get_svg_icon("check", "#4fae4e", 16))