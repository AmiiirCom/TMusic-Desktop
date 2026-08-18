from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class LyricsDialog(QDialog):
    """Telegram Desktop styled modal displaying synchronized/unsynchronized song lyrics."""

    def __init__(self, title: str, artist: str, lyrics: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._lyrics = lyrics
        self.setWindowTitle(f"متن آهنگ: {title}")
        self.resize(480, 560)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._init_ui(title, artist)

    def _init_ui(self, title: str, artist: str) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #17212b;
                color: #ffffff;
            }
            QLabel {
                font-family: 'Vazirmatn', 'Segoe UI', sans-serif;
            }
            QTextEdit {
                background-color: #0e1621;
                border: 1px solid #242f3d;
                border-radius: 8px;
                color: #e4ecf2;
                font-family: 'Vazirmatn', 'Segoe UI', sans-serif;
                font-size: 14px;
                line-height: 1.8;
                padding: 16px;
                selection-background-color: #2481cc;
            }
            QPushButton {
                background-color: #2481cc;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #1d72b8; }
            QPushButton#btnCopy {
                background-color: #242f3d;
                color: #6ab3f3;
                border: 1px solid #2f3e50;
            }
            QPushButton#btnCopy:hover { background-color: #2f3e50; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header Title & Artist
        header_layout = QVBoxLayout()
        header_layout.setSpacing(2)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #6ab3f3;")

        artist_lbl = QLabel(artist)
        artist_lbl.setStyleSheet("font-size: 12px; color: #7f91a4;")

        header_layout.addWidget(title_lbl)
        header_layout.addWidget(artist_lbl)
        layout.addLayout(header_layout)

        # Lyrics Text Box
        self.text_box = QTextEdit()
        self.text_box.setReadOnly(True)
        self.text_box.setPlainText(self._lyrics)
        layout.addWidget(self.text_box)

        # Actions Row
        actions_layout = QHBoxLayout()

        self.btn_copy = QPushButton("📋 کپی متن آهنگ")
        self.btn_copy.setObjectName("btnCopy")
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.clicked.connect(self._on_copy_lyrics)

        btn_close = QPushButton("بستن")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.accept)

        actions_layout.addWidget(self.btn_copy)
        actions_layout.addStretch()
        actions_layout.addWidget(btn_close)
        layout.addLayout(actions_layout)

    def _on_copy_lyrics(self) -> None:
        QApplication.clipboard().setText(self._lyrics)
        self.btn_copy.setText("✅ کپی شد!")