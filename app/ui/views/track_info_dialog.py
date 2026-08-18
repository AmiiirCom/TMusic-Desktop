from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.core.metadata import AudioMetadata
from app.models.track import Track
from app.ui.components.player_bar import create_playerbar_cover_pixmap
from app.ui.views.base_modal import BaseModalDialog


class TrackInfoDialog(BaseModalDialog):
    """Frameless unified modal displaying authentic audio file metadata."""

    def __init__(self, track: Track, metadata: AudioMetadata | None, parent: QWidget | None = None) -> None:
        super().__init__(title="مشخصات و متادیتای آهنگ", parent=parent)
        self.card_frame.setFixedWidth(460)
        self._init_body(track, metadata or AudioMetadata())

    def _init_body(self, track: Track, meta: AudioMetadata) -> None:
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
        self.body_layout.addLayout(top_layout)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #242f3d; margin: 4px 0;")
        self.body_layout.addWidget(sep)

        # Metadata Form
        form = QFormLayout()
        form.setSpacing(9)

        def add_row(key: str, val: str) -> None:
            if val and str(val).strip():
                k = QLabel(key)
                k.setStyleSheet("color: #7f91a4; font-weight: bold; font-size: 13px;")
                v = QLabel(str(val))
                v.setStyleSheet("color: #e4ecf2; font-size: 13px;")
                v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                form.addRow(k, v)

        add_row("نام آهنگ (Title):", meta.title or track.title)
        add_row("خواننده (Artist):", meta.artist or track.artist)
        add_row("آلبوم (Album):", meta.album)
        add_row("سبک (Genre):", meta.genre)
        add_row("آهنگساز (Composer):", meta.composer)
        add_row("ناشر (Publisher):", meta.publisher)
        add_row("شماره ترک در آلبوم:", meta.track_number)

        if meta.release_date:
            add_row("📅 سال انتشار اثر:", meta.release_date)

        add_row("مدت زمان:", track.formatted_duration)
        add_row("حجم فایل:", track.formatted_size)
        if meta.bitrate_kbps > 0:
            add_row("بیت‌ریت (Bitrate):", f"{meta.bitrate_kbps} kb/s")

        if track.formatted_date:
            add_row("تاریخ ارسال در تلگرام:", track.formatted_date)

        if track.local_path:
            add_row("نام فایل در سیستم:", Path(track.local_path).name)

        self.body_layout.addLayout(form)