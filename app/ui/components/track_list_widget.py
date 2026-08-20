from pathlib import Path
from typing import Any
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models.track import Track
from app.ui.utils.icons import get_svg_icon


def create_rounded_cover_pixmap(
    minithumb_data: bytes | None = None,
    cover_path: str | None = None,
    size: int = 44,
    is_active: bool = False,
) -> QPixmap:
    scale = 2
    render_size = size * scale
    target_pixmap = QPixmap(render_size, render_size)
    target_pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(target_pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    path = QPainterPath()
    path.addRoundedRect(0, 0, render_size, render_size, 8 * scale, 8 * scale)
    painter.setClipPath(path)

    has_drawn = False

    if cover_path and Path(cover_path).exists():
        src = QPixmap(str(cover_path))
        if not src.isNull():
            scaled = src.scaled(
                render_size,
                render_size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - render_size) // 2
            y = (scaled.height() - render_size) // 2
            painter.drawPixmap(0, 0, scaled.copy(x, y, render_size, render_size))
            has_drawn = True

    if not has_drawn and minithumb_data:
        src = QPixmap()
        if src.loadFromData(minithumb_data):
            scaled = src.scaled(
                render_size,
                render_size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - render_size) // 2
            y = (scaled.height() - render_size) // 2
            painter.drawPixmap(0, 0, scaled.copy(x, y, render_size, render_size))
            has_drawn = True

    if not has_drawn:
        bg_color = QColor("#2481cc" if is_active else "#2b5278")
        painter.fillRect(0, 0, render_size, render_size, bg_color)
        painter.setPen(QColor("#ffffff"))
        font = QFont("Vazirmatn", 16 * scale, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(target_pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "🎵")

    if is_active:
        badge_size = 18 * scale
        badge_x = render_size - badge_size - (3 * scale)
        badge_y = render_size - badge_size - (3 * scale)

        painter.setClipping(False)
        painter.setBrush(QColor(79, 174, 78, 230))
        painter.setPen(QPen(QColor("#ffffff"), 1 * scale))
        painter.drawEllipse(badge_x, badge_y, badge_size, badge_size)

        painter.setPen(QColor("#ffffff"))
        font_icon = QFont("Segoe UI Emoji", 9 * scale, QFont.Weight.Bold)
        painter.setFont(font_icon)
        painter.drawText(badge_x, badge_y, badge_size, badge_size, Qt.AlignmentFlag.AlignCenter, "🔊")

    painter.end()
    target_pixmap.setDevicePixelRatio(scale)
    return target_pixmap


class TrackItemWidget(QWidget):
    """Custom Telegram-styled track list item with like button and smooth visual transitions."""

    like_clicked = Signal(Track)

    def __init__(self, track: Track, is_active: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.track = track
        self._is_active = is_active
        self._cover_path: str | None = track.cover_path
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
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
        self.btn_like.setIconSize(QSize(16, 16))
        self.btn_like.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_like.clicked.connect(self._on_like_clicked)

        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(2)
        meta_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

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

    def _on_like_clicked(self) -> None:
        self.like_clicked.emit(self.track)

    def set_active_state(self, is_active: bool) -> None:
        if self._is_active == is_active:
            return
        self._is_active = is_active
        self._apply_visual_state()

    def update_reaction(self, is_liked: bool, heart_count: int) -> None:
        self.track = Track(
            id=self.track.id,
            chat_id=self.track.chat_id,
            message_id=self.track.message_id,
            file_id=self.track.file_id,
            title=self.track.title,
            artist=self.track.artist,
            duration_seconds=self.track.duration_seconds,
            size_bytes=self.track.size_bytes,
            file_name=self.track.file_name,
            mime_type=self.track.mime_type,
            local_path=self.track.local_path,
            is_downloaded=self.track.is_downloaded,
            date_timestamp=self.track.date_timestamp,
            minithumbnail_data=self.track.minithumbnail_data,
            cover_file_id=self.track.cover_file_id,
            cover_path=self._cover_path,
            is_liked=is_liked,
            heart_count=heart_count,
        )
        self._apply_like_state()

    def _apply_like_state(self) -> None:
        if self.track.is_liked:
            self.btn_like.setIcon(get_svg_icon("heart_filled", "#e53935", 16))
            tip = f"{self.tr('Liked')} ({self.track.heart_count})" if self.track.heart_count > 0 else self.tr("Liked")
            self.btn_like.setToolTip(tip)
            self.btn_like.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                }
                QPushButton:hover {
                    background-color: rgba(229, 57, 53, 0.15);
                    border-radius: 16px;
                }
            """)
        else:
            self.btn_like.setIcon(get_svg_icon("heart_outline", "#7f91a4", 16))
            tip = f"{self.tr('Like')} ({self.track.heart_count})" if self.track.heart_count > 0 else self.tr("Like")
            self.btn_like.setToolTip(tip)
            self.btn_like.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.1);
                    border-radius: 16px;
                }
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
                TrackItemWidget:hover {
                    background-color: #17212b;
                }
            """)
            self.title_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold; background: transparent; border: none;")
            self.artist_label.setStyleSheet("color: #7f91a4; font-size: 12px; background: transparent; border: none;")
            self.duration_label.setStyleSheet("color: #7f91a4; font-size: 13px; font-weight: bold; background: transparent; border: none;")
            self.meta_sub_label.setStyleSheet("color: #5d6e80; font-size: 11px; background: transparent; border: none;")

        self.update_cover(self._cover_path)

    def update_cover(self, cover_path: str | None) -> None:
        if cover_path:
            self._cover_path = cover_path
            if self.track.cover_path != cover_path:
                self.track = Track(
                    id=self.track.id,
                    chat_id=self.track.chat_id,
                    message_id=self.track.message_id,
                    file_id=self.track.file_id,
                    title=self.track.title,
                    artist=self.track.artist,
                    duration_seconds=self.track.duration_seconds,
                    size_bytes=self.track.size_bytes,
                    file_name=self.track.file_name,
                    mime_type=self.track.mime_type,
                    local_path=self.track.local_path,
                    is_downloaded=self.track.is_downloaded,
                    date_timestamp=self.track.date_timestamp,
                    minithumbnail_data=self.track.minithumbnail_data,
                    cover_file_id=self.track.cover_file_id,
                    cover_path=cover_path,
                    is_liked=self.track.is_liked,
                    heart_count=self.track.heart_count,
                )

        pixmap = create_rounded_cover_pixmap(
            minithumb_data=self.track.minithumbnail_data,
            cover_path=self._cover_path,
            size=44,
            is_active=self._is_active,
        )
        self.cover_label.setPixmap(pixmap)


class TrackListWidget(QListWidget):
    """List widget with robust widget deletion, fast pagination, and smooth cover transitions."""

    track_selected = Signal(Track)
    track_like_toggled = Signal(Track)
    load_more_requested = Signal()
    search_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._all_tracks: list[Track] = []
        self._track_widgets: dict[str, TrackItemWidget] = {}
        self._active_track_id: str | None = None
        self._current_query: str = ""
        self._has_more: bool = True
        self._is_loading_more: bool = False

        self.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        self.setStyleSheet("""
            QListWidget {
                background-color: #0e1621;
                border: none;
                outline: none;
            }
            QListWidget::item {
                border-bottom: 1px solid #141c26;
                background-color: transparent;
                padding: 2px 6px;
            }
            QListWidget::item:hover {
                background-color: transparent;
            }
            QListWidget::item:selected {
                background-color: transparent;
            }
        """)

        self.itemClicked.connect(self._on_item_clicked)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            event.ignore()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            event.ignore()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: Any) -> None:
        event.ignore()

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
                item.setData(Qt.ItemDataRole.UserRole, track.id)
                is_active = track.id == self._active_track_id
                widget = TrackItemWidget(track, is_active=is_active)
                widget.like_clicked.connect(self.track_like_toggled.emit)
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
                item.setData(Qt.ItemDataRole.UserRole, track.id)
                is_active = track.id == self._active_track_id
                widget = TrackItemWidget(track, is_active=is_active)
                widget.like_clicked.connect(self.track_like_toggled.emit)
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
            for i in range(self.count()):
                item = self.item(i)
                if item and (item.data(Qt.ItemDataRole.UserRole) == tid or self.itemWidget(item) == widget):
                    self.removeItemWidget(item)
                    taken = self.takeItem(i)
                    if widget:
                        widget.hide()
                        widget.setParent(None)
                        widget.deleteLater()
                    if taken:
                        del taken
                    break

        self.viewport().update()

    def update_track_reaction(self, chat_id: int, message_id: int, is_liked: bool, heart_count: int) -> None:
        track_id = f"{chat_id}_{message_id}"
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
                    cover_path=t.cover_path,
                    is_liked=is_liked,
                    heart_count=heart_count,
                )
                break

        widget = self._track_widgets.get(track_id)
        if widget:
            widget.update_reaction(is_liked, heart_count)

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
                    is_liked=t.is_liked,
                    heart_count=t.heart_count,
                )
                break

        widget = self._track_widgets.get(track_id)
        if widget:
            widget.update_cover(cover_path)

    def set_active_track(self, track: Track | None) -> None:
        new_id = track.id if track else None
        old_id = self._active_track_id

        if old_id == new_id:
            return

        if old_id and old_id in self._track_widgets:
            self._track_widgets[old_id].set_active_state(False)

        if new_id and new_id in self._track_widgets:
            self._track_widgets[new_id].set_active_state(True)

        self._active_track_id = new_id

    def filter_tracks(self, query: str) -> None:
        self._current_query = query.strip().lower()
        if not self._current_query:
            self._populate(self._all_tracks)
        else:
            filtered = [
                t
                for t in self._all_tracks
                if self._current_query in t.display_title.lower()
                or self._current_query in t.display_artist.lower()
            ]
            self._populate(filtered)
        self.search_requested.emit(query.strip())

    def _populate(self, tracks: list[Track]) -> None:
        self.clear()
        self._track_widgets.clear()
        for track in tracks:
            item = QListWidgetItem(self)
            item.setData(Qt.ItemDataRole.UserRole, track.id)
            is_active = track.id == self._active_track_id
            widget = TrackItemWidget(track, is_active=is_active)
            widget.like_clicked.connect(self.track_like_toggled.emit)
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

    def scroll_to_track(self, track_id: str) -> None:
        if track_id not in self._track_widgets:
            return
        widget = self._track_widgets[track_id]
        for i in range(self.count()):
            item = self.item(i)
            if self.itemWidget(item) == widget:
                self.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
                break