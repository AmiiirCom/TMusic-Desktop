from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.track import Track


class TrackItemWidget(QWidget):
    """Custom Telegram-styled track list item with playing indicator."""

    def __init__(self, track: Track, is_active: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.track = track
        self._is_active = is_active
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(14)

        icon_text = "🔊" if self._is_active else "▶"
        icon_bg = "#4fae4e" if self._is_active else "#2481cc"

        self.icon_label = QLabel(icon_text)
        self.icon_label.setFixedSize(38, 38)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet(f"""
            QLabel {{
                background-color: {icon_bg};
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                border-radius: 19px;
            }}
        """)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        title_color = "#6ab3f3" if self._is_active else "#ffffff"
        self.title_label = QLabel(self.track.display_title)
        self.title_label.setStyleSheet(f"color: {title_color}; font-size: 14px; font-weight: bold;")

        self.artist_label = QLabel(self.track.display_artist)
        self.artist_label.setStyleSheet("color: #7f91a4; font-size: 12px;")

        info_layout.addWidget(self.title_label)
        info_layout.addWidget(self.artist_label)

        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(2)
        meta_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        duration_label = QLabel(self.track.formatted_duration)
        duration_label.setStyleSheet("color: #6ab3f3; font-size: 13px; font-weight: bold;")
        duration_label.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        size_label = QLabel(self.track.formatted_size)
        size_label.setStyleSheet("color: #5d6e80; font-size: 11px;")
        size_label.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        meta_layout.addWidget(duration_label)
        meta_layout.addWidget(size_label)

        layout.addWidget(self.icon_label)
        layout.addLayout(info_layout)
        layout.addStretch()
        layout.addLayout(meta_layout)


class TrackListWidget(QListWidget):
    """List widget holding the tracks with live playing indicators and infinite scroll."""

    track_selected = Signal(Track)
    load_more_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._all_tracks: list[Track] = []
        self._active_track_id: str | None = None
        self._current_query: str = ""
        self._has_more: bool = True
        self._is_loading_more: bool = False

        self.setStyleSheet("""
            QListWidget {
                background-color: #0e1621;
                border: none;
                outline: none;
            }
            QListWidget::item {
                border-bottom: 1px solid #17212b;
                background-color: transparent;
            }
            QListWidget::item:hover {
                background-color: #17212b;
            }
            QListWidget::item:selected {
                background-color: #1d2a3a;
            }
        """)
        self.itemDoubleClicked.connect(self._on_item_clicked)
        self.itemClicked.connect(self._on_item_clicked)

        # Detect infinite scrolling
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def set_tracks(self, tracks: list[Track], has_more: bool = True) -> None:
        """Reset and load initial chunk of tracks."""
        self._all_tracks = list(tracks)
        self._has_more = has_more
        self._is_loading_more = False
        self._populate(self._all_tracks)

    def append_tracks(self, new_tracks: list[Track], has_more: bool = True) -> None:
        """Append lazy chunk of tracks smoothly without resetting scroll position."""
        self._has_more = has_more
        self._is_loading_more = False

        # Add only unique tracks
        existing_ids = {t.id for t in self._all_tracks}
        unique_new = [t for t in new_tracks if t.id not in existing_ids]
        self._all_tracks.extend(unique_new)

        if not self._current_query:
            for track in unique_new:
                item = QListWidgetItem(self)
                is_active = (track.id == self._active_track_id)
                widget = TrackItemWidget(track, is_active=is_active)
                item.setSizeHint(widget.sizeHint())
                self.addItem(item)
                self.setItemWidget(item, widget)
        else:
            self.filter_tracks(self._current_query)

    def set_active_track(self, track: Track | None) -> None:
        self._active_track_id = track.id if track else None
        self.filter_tracks(self._current_query)

    def filter_tracks(self, query: str) -> None:
        self._current_query = query.strip().lower()
        if not self._current_query:
            self._populate(self._all_tracks)
            return

        filtered = [
            t
            for t in self._all_tracks
            if self._current_query in t.display_title.lower()
            or self._current_query in t.display_artist.lower()
        ]
        self._populate(filtered)

    def _populate(self, tracks: list[Track]) -> None:
        self.clear()
        for track in tracks:
            item = QListWidgetItem(self)
            is_active = (track.id == self._active_track_id)
            widget = TrackItemWidget(track, is_active=is_active)
            item.setSizeHint(widget.sizeHint())
            self.addItem(item)
            self.setItemWidget(item, widget)

    def _on_scroll(self, value: int) -> None:
        """Trigger lazy loading when scrolling reaches near bottom."""
        max_val = self.verticalScrollBar().maximum()
        # If user scrolled within 30px of bottom, request next chunk
        if (max_val - value <= 30) and self._has_more and not self._is_loading_more and not self._current_query:
            self._is_loading_more = True
            self.load_more_requested.emit()

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        widget = self.itemWidget(item)
        if isinstance(widget, TrackItemWidget):
            self.track_selected.emit(widget.track)