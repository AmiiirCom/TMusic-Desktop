from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
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
from app.ui.components.marquee_label import MarqueeLabel
from app.ui.utils.pixmaps import create_rounded_cover_pixmap
from app.ui.views.base_modal import BaseModalDialog


class TrackInfoDialog(BaseModalDialog):
    """Frameless modal dialog displaying detailed track tags with marquee headers."""

    def __init__(self, track: Track, metadata: AudioMetadata | None, parent: QWidget | None = None) -> None:
        super().__init__(title="Track Details", parent=parent)
        self.card_frame.setFixedWidth(460)
        self._init_body(track, metadata or AudioMetadata())

    def _init_body(self, track: Track, meta: AudioMetadata) -> None:
        top_layout = QHBoxLayout()
        top_layout.setSpacing(16)

        cover_lbl = QLabel()
        cover_lbl.setFixedSize(64, 64)
        cover_lbl.setPixmap(create_rounded_cover_pixmap(track.minithumbnail_data, track.cover_path, size=64))

        title_box = QVBoxLayout()
        title_box.setSpacing(3)

        # Sliding Marquee Title in Dialog Header
        t_lbl = MarqueeLabel(meta.title or track.display_title, fade_width=16, speed_px_per_sec=30)
        t_lbl.setFixedHeight(22)
        t_font = QFont("Segoe UI", 11, QFont.Weight.Bold)
        t_lbl.setFont(t_font)
        t_lbl.setTextColor("#6ab3f3")

        # Sliding Marquee Artist in Dialog Header
        a_lbl = MarqueeLabel(meta.artist or track.display_artist, fade_width=14, speed_px_per_sec=26)
        a_lbl.setFixedHeight(18)
        a_font = QFont("Segoe UI", 9)
        a_lbl.setFont(a_font)
        a_lbl.setTextColor("#7f91a4")

        title_box.addWidget(t_lbl)
        title_box.addWidget(a_lbl)

        top_layout.addWidget(cover_lbl)
        top_layout.addLayout(title_box, stretch=1)
        self.body_layout.addLayout(top_layout)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #242f3d; margin: 4px 0;")
        self.body_layout.addWidget(sep)

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

        add_row(self.tr("Title:"), meta.title or track.title)
        add_row(self.tr("Artist:"), meta.artist or track.artist)
        add_row(self.tr("Album:"), meta.album)
        add_row(self.tr("Genre:"), meta.genre)
        add_row(self.tr("Composer:"), meta.composer)
        add_row(self.tr("Publisher:"), meta.publisher)
        add_row(self.tr("Track Number:"), meta.track_number)

        if meta.release_date:
            add_row(self.tr("Release Date:"), meta.release_date)

        add_row(self.tr("Duration:"), track.formatted_duration)
        add_row(self.tr("File Size:"), track.formatted_size)
        if meta.bitrate_kbps > 0:
            add_row(self.tr("Bitrate:"), f"{meta.bitrate_kbps} kb/s")

        if track.formatted_date:
            add_row(self.tr("Telegram Date:"), track.formatted_date)

        self.body_layout.addLayout(form)