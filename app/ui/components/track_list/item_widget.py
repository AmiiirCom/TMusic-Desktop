from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models.track import Track
from app.ui.utils.pixmaps import create_rounded_cover_pixmap


class TrackItemWidget(QWidget):
    """Custom Telegram-styled track list item with like button and visual highlight."""

    like_clicked = Signal(Track)

    def __init__(self, track: Track, is_active: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.track = track
        self._is_active = is_active
        self._cover_path: str | None = track.cover_path
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(12)

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(44, 44)
        self.cover_label.setStyleSheet("background: transparent; border: none;")

        info_layout = QVBoxLayout()
        info_layout.setSpacing(3)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.title_label = QLabel(self.track.display_title)
        self.artist_label = QLabel(self.track.display_artist)

        info_layout.addWidget(self.title_label)
        info_layout.addWidget(self.artist_label)

        self.btn_like = QPushButton()
        self.btn_like.setFixedSize(32, 32)
        self.btn_like.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_like.clicked.connect(lambda: self.like_clicked.emit(self.track))

        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(2)
        meta_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        self.duration_label = QLabel(self.track.formatted_duration)
        self.duration_label.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        meta_text = (
            f"{self.track.formatted_size} • {self.track.formatted_date}"
            if self.track.formatted_date
            else self.track.formatted_size
        )
        self.meta_sub_label = QLabel(meta_text)
        self.meta_sub_label.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        meta_layout.addWidget(self.duration_label)
        meta_layout.addWidget(self.meta_sub_label)

        layout.addWidget(self.cover_label)
        layout.addLayout(info_layout)
        layout.addStretch()
        layout.addWidget(self.btn_like)
        layout.addLayout(meta_layout)

        self._apply_visual_state()
        self._apply_like_state()

    def set_active_state(self, is_active: bool) -> None:
        if self._is_active == is_active:
            return
        self._is_active = is_active
        self._apply_visual_state()

    def update_reaction(self, is_liked: bool, heart_count: int) -> None:
        self.track = self._clone_track(self.track, is_liked=is_liked, heart_count=heart_count)
        self._apply_like_state()

    def update_cover(self, cover_path: str | None) -> None:
        if cover_path:
            self._cover_path = cover_path
            if self.track.cover_path != cover_path:
                self.track = self._clone_track(self.track, cover_path=cover_path)

        pixmap = create_rounded_cover_pixmap(
            minithumb_data=self.track.minithumbnail_data,
            cover_path=self._cover_path,
            size=44,
            is_active=self._is_active,
        )
        self.cover_label.setPixmap(pixmap)

    def _apply_like_state(self) -> None:
        if self.track.is_liked:
            self.btn_like.setText("❤️")
            tip = f"پسندیده‌اید ({self.track.heart_count})" if self.track.heart_count > 0 else "پسندیده‌اید"
            self.btn_like.setToolTip(tip)
            self.btn_like.setStyleSheet("""
                QPushButton { background: transparent; border: none; font-size: 16px; }
                QPushButton:hover { background-color: rgba(229, 57, 53, 0.15); border-radius: 16px; }
            """)
        else:
            self.btn_like.setText("🤍")
            tip = f"پسندیدن ({self.track.heart_count})" if self.track.heart_count > 0 else "پسندیدن"
            self.btn_like.setToolTip(tip)
            self.btn_like.setStyleSheet("""
                QPushButton { background: transparent; border: none; font-size: 15px; opacity: 0.7; }
                QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); border-radius: 16px; }
            """)

    def _apply_visual_state(self) -> None:
        if self._is_active:
            self.setStyleSheet("""
                TrackItemWidget {
                    background-color: #20354b;
                    border: 1.5px solid #2481cc;
                    border-radius: 8px;
                }
            """)
            self.title_label.setStyleSheet("color: #52a3ff; font-size: 14px; font-weight: bold; background: transparent; border: none;")
            self.artist_label.setStyleSheet("color: #9ec6ed; font-size: 12px; background: transparent; border: none;")
            self.duration_label.setStyleSheet("color: #52a3ff; font-size: 13px; font-weight: bold; background: transparent; border: none;")
            self.meta_sub_label.setStyleSheet("color: #8db3d6; font-size: 11px; background: transparent; border: none;")
        else:
            self.setStyleSheet("""
                TrackItemWidget {
                    background-color: transparent;
                    border: 1.5px solid transparent;
                    border-radius: 8px;
                }
                TrackItemWidget:hover { background-color: #17212b; }
            """)
            self.title_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold; background: transparent; border: none;")
            self.artist_label.setStyleSheet("color: #7f91a4; font-size: 12px; background: transparent; border: none;")
            self.duration_label.setStyleSheet("color: #7f91a4; font-size: 13px; font-weight: bold; background: transparent; border: none;")
            self.meta_sub_label.setStyleSheet("color: #5d6e80; font-size: 11px; background: transparent; border: none;")

        self.update_cover(self._cover_path)

    @staticmethod
    def _clone_track(t: Track, **kwargs) -> Track:
        data = {
            "id": t.id, "chat_id": t.chat_id, "message_id": t.message_id, "file_id": t.file_id,
            "title": t.title, "artist": t.artist, "duration_seconds": t.duration_seconds,
            "size_bytes": t.size_bytes, "file_name": t.file_name, "mime_type": t.mime_type,
            "local_path": t.local_path, "is_downloaded": t.is_downloaded, "date_timestamp": t.date_timestamp,
            "minithumbnail_data": t.minithumbnail_data, "cover_file_id": t.cover_file_id,
            "cover_path": t.cover_path, "is_liked": t.is_liked, "heart_count": t.heart_count,
        }
        data.update(kwargs)
        return Track(**data)