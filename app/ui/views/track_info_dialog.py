from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.metadata import AudioMetadata
from app.models.track import Track
from app.ui.components.player_bar import create_playerbar_cover_pixmap


class TrackInfoDialog(QDialog):
    """Telegram Desktop styled modal displaying authentic audio file metadata."""

    def __init__(self, track: Track, metadata: AudioMetadata | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("مشخصات و متادیتای آهنگ")
        self.resize(460, 520)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._init_ui(track, metadata or AudioMetadata())

    def _init_ui(self, track: Track, meta: AudioMetadata) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #17212b;
                color: #ffffff;
            }
            QLabel {
                font-family: 'Vazirmatn', 'Segoe UI', sans-serif;
                font-size: 13px;
                color: #ffffff;
            }
            QLabel#metaKey {
                color: #7f91a4;
                font-weight: bold;
            }
            QLabel#metaVal {
                color: #e4ecf2;
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
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        # 1. Top Section: HD Artwork + Title & Artist
        top_layout = QHBoxLayout()
        top_layout.setSpacing(16)

        cover_lbl = QLabel()
        cover_lbl.setFixedSize(64, 64)
        cover_lbl.setPixmap(create_playerbar_cover_pixmap(track.minithumbnail_data, track.cover_path, size=64))

        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        t_lbl = QLabel(meta.title or track.display_title)
        t_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #6ab3f3;")
        a_lbl = QLabel(meta.artist or track.display_artist)
        a_lbl.setStyleSheet("font-size: 12px; color: #7f91a4;")
        title_box.addWidget(t_lbl)
        title_box.addWidget(a_lbl)

        top_layout.addWidget(cover_lbl)
        top_layout.addLayout(title_box)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #242f3d;")
        layout.addWidget(sep)

        # 2. Form for Audio Embedded Tags
        form = QFormLayout()
        form.setSpacing(10)

        def add_row(key: str, val: str) -> None:
            if val and val.strip():
                k = QLabel(key)
                k.setObjectName("metaKey")
                v = QLabel(val)
                v.setObjectName("metaVal")
                v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                form.addRow(k, v)

        add_row("نام آهنگ (Title):", meta.title or track.title)
        add_row("خواننده (Artist):", meta.artist or track.artist)
        add_row("آلبوم (Album):", meta.album)
        add_row("سبک (Genre):", meta.genre)
        add_row("آهنگساز (Composer):", meta.composer)
        add_row("ناشر (Publisher):", meta.publisher)
        add_row("شماره ترک در آلبوم:", meta.track_number)

        # Authentic File Release Date (From ID3 Tag)
        if meta.release_date:
            add_row("📅 سال انتشار اثر:", meta.release_date)

        # Technical file info
        add_row("مدت زمان:", track.formatted_duration)
        add_row("حجم فایل:", track.formatted_size)
        if meta.bitrate_kbps > 0:
            add_row("بیت‌ریت (Bitrate):", f"{meta.bitrate_kbps} kb/s")

        # Telegram Message Info
        if track.formatted_date:
            add_row("تاریخ ارسال در تلگرام:", track.formatted_date)

        if track.local_path:
            add_row("نام فایل در سیستم:", Path(track.local_path).name)

        layout.addLayout(form)
        layout.addStretch()

        # Close button
        btn_close = QPushButton("بستن")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)