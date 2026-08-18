from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.track import Track


def create_rounded_cover_pixmap(
    minithumb_data: bytes | None = None,
    cover_path: str | None = None,
    size: int = 44,
    is_active: bool = False,
) -> QPixmap:
    target_pixmap = QPixmap(size, size)
    target_pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(target_pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    path = QPainterPath()
    path.addRoundedRect(0, 0, size, size, 8, 8)
    painter.setClipPath(path)

    has_drawn = False

    if cover_path and Path(cover_path).exists():
        src = QPixmap(str(cover_path))
        if not src.isNull():
            scaled = src.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - size) // 2
            y = (scaled.height() - size) // 2
            painter.drawPixmap(0, 0, scaled.copy(x, y, size, size))
            has_drawn = True

    if not has_drawn and minithumb_data:
        src = QPixmap()
        if src.loadFromData(minithumb_data):
            scaled = src.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - size) // 2
            y = (scaled.height() - size) // 2
            painter.drawPixmap(0, 0, scaled.copy(x, y, size, size))
            has_drawn = True

    if not has_drawn:
        bg_color = QColor("#2b5278" if not is_active else "#2481cc")
        painter.fillRect(0, 0, size, size, bg_color)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(target_pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "🎵")

    if is_active:
        painter.setBrush(QColor(79, 174, 78, 220))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(size - 18, size - 18, 16, 16)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(size - 18, size - 18, 16, 16, Qt.AlignmentFlag.AlignCenter, "▶")

    painter.end()
    return target_pixmap


class TrackItemWidget(QWidget):
    """Custom Telegram-styled track list item with exclusive active playback highlighting."""

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

        # Subtle row highlight ONLY for the currently playing track
        if self._is_active:
            self.setStyleSheet("""
                TrackItemWidget {
                    background-color: #172433;
                    border-radius: 8px;
                }
            """)
        else:
            self.setStyleSheet("""
                TrackItemWidget {
                    background-color: transparent;
                }
            """)

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(44, 44)
        self.update_cover(self.track.cover_path)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(3)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        title_color = "#6ab3f3" if self._is_active else "#ffffff"
        self.title_label = QLabel(self.track.display_title)
        self.title_label.setStyleSheet(f"color: {title_color}; font-size: 14px; font-weight: bold; background: transparent;")

        self.artist_label = QLabel(self.track.display_artist)
        self.artist_label.setStyleSheet("color: #7f91a4; font-size: 12px; background: transparent;")

        info_layout.addWidget(self.title_label)
        info_layout.addWidget(self.artist_label)

        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(2)
        meta_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        duration_label = QLabel(self.track.formatted_duration)
        duration_label.setStyleSheet("color: #6ab3f3; font-size: 13px; font-weight: bold; background: transparent;")
        duration_label.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        meta_text = (
            f"{self.track.formatted_size} • {self.track.formatted_date}"
            if self.track.formatted_date
            else self.track.formatted_size
        )
        meta_sub_label = QLabel(meta_text)
        meta_sub_label.setStyleSheet("color: #5d6e80; font-size: 11px; background: transparent;")
        meta_sub_label.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        meta_layout.addWidget(duration_label)
        meta_layout.addWidget(meta_sub_label)

        layout.addWidget(self.cover_label)
        layout.addLayout(info_layout)
        layout.addStretch()
        layout.addLayout(meta_layout)

    def update_cover(self, cover_path: str | None) -> None:
        pixmap = create_rounded_cover_pixmap(
            minithumb_data=self.track.minithumbnail_data,
            cover_path=cover_path or self.track.cover_path,
            size=44,
            is_active=self._is_active,
        )
        self.cover_label.setPixmap(pixmap)


class TrackListWidget(QListWidget):
    """List widget holding the tracks with NO default selection highlight on right-click."""

    track_selected = Signal(Track)
    load_more_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._all_tracks: list[Track] = []
        self._track_widgets: dict[str, TrackItemWidget] = {}
        self._active_track_id: str | None = None
        self._current_query: str = ""
        self._has_more: bool = True
        self._is_loading_more: bool = False

        # Disable default list selection box completely
        self.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.setStyleSheet("""
            QListWidget {
                background-color: #0e1621;
                border: none;
                outline: none;
            }
            QListWidget::item {
                border-bottom: 1px solid #17212b;
                background-color: transparent;
                padding: 0px;
                margin: 0px;
            }
            QListWidget::item:hover {
                background-color: #17212b;
            }
            QListWidget::item:selected {
                background-color: transparent;
            }
        """)
        self.itemDoubleClicked.connect(self._on_item_clicked)
        self.itemClicked.connect(self._on_item_clicked)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def set_tracks(self, tracks: list[Track], has_more: bool = True) -> None:
        self._all_tracks = list(tracks)
        self._has_more = has_more
        self._is_loading_more = False
        self._populate(self._all_tracks)

    def append_tracks(self, new_tracks: list[Track], has_more: bool = True) -> None:
        self._has_more = has_more
        self._is_loading_more = False

        existing_ids = {t.id for t in self._all_tracks}
        unique_new = [t for t in new_tracks if t.id not in existing_ids]
        self._all_tracks.extend(unique_new)

        if not self._current_query:
            for track in unique_new:
                item = QListWidgetItem(self)
                is_active = track.id == self._active_track_id
                widget = TrackItemWidget(track, is_active=is_active)
                item.setSizeHint(widget.sizeHint())
                self.addItem(item)
                self.setItemWidget(item, widget)
                self._track_widgets[track.id] = widget
        else:
            self.filter_tracks(self._current_query)

    def prepend_tracks(self, new_tracks: list[Track]) -> None:
        existing_ids = {t.id for t in self._all_tracks}
        unique_new = [t for t in new_tracks if t.id not in existing_ids]
        if not unique_new:
            return

        self._all_tracks = unique_new + self._all_tracks

        if not self._current_query:
            for idx, track in enumerate(unique_new):
                item = QListWidgetItem()
                is_active = track.id == self._active_track_id
                widget = TrackItemWidget(track, is_active=is_active)
                item.setSizeHint(widget.sizeHint())
                self.insertItem(idx, item)
                self.setItemWidget(item, widget)
                self._track_widgets[track.id] = widget
        else:
            self.filter_tracks(self._current_query)

    def remove_tracks(self, deleted_track_ids: list[str]) -> None:
        del_set = set(deleted_track_ids)
        self._all_tracks = [t for t in self._all_tracks if t.id not in del_set]

        for tid in deleted_track_ids:
            widget = self._track_widgets.pop(tid, None)
            if widget:
                for i in range(self.count()):
                    item = self.item(i)
                    if self.itemWidget(item) == widget:
                        self.takeItem(i)
                        break

    def update_track_cover(self, track_id: str, cover_path: str) -> None:
        for idx, t in enumerate(self._all_tracks):
            if t.id == track_id:
                self._all_tracks[idx] = Track(
                    id=t.id,
                    chat_id=t.chat_id,
                    message_id=t.message_id,
                    file_id=t.file_id,
                    title=t.title,
                    artist=t.artist,
                    duration_seconds=t.duration_seconds,
                    size_bytes=t.size_bytes,
                    file_name=t.file_name,
                    mime_type=t.mime_type,
                    local_path=t.local_path,
                    is_downloaded=t.is_downloaded,
                    date_timestamp=t.date_timestamp,
                    minithumbnail_data=t.minithumbnail_data,
                    cover_file_id=t.cover_file_id,
                    cover_path=cover_path,
                )
                break

        widget = self._track_widgets.get(track_id)
        if widget:
            widget.update_cover(cover_path)

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
        self._track_widgets.clear()
        for track in tracks:
            item = QListWidgetItem(self)
            is_active = track.id == self._active_track_id
            widget = TrackItemWidget(track, is_active=is_active)
            item.setSizeHint(widget.sizeHint())
            self.addItem(item)
            self.setItemWidget(item, widget)
            self._track_widgets[track.id] = widget

    def _on_scroll(self, value: int) -> None:
        max_val = self.verticalScrollBar().maximum()
        if (max_val - value <= 30) and self._has_more and not self._is_loading_more and not self._current_query:
            self._is_loading_more = True
            self.load_more_requested.emit()

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        widget = self.itemWidget(item)
        if isinstance(widget, TrackItemWidget):
            self.track_selected.emit(widget.track)