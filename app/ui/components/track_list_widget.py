from typing import Any
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont, QMouseEvent
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
from app.ui.components.marquee_label import MarqueeLabel
from app.ui.utils.icons import get_svg_icon
from app.ui.utils.pixmaps import create_rounded_cover_pixmap


class TrackItemWidget(QWidget):
    """Custom Telegram-styled track list item with transparent backgrounds and marquee labels."""

    like_clicked = Signal(Track)

    def __init__(self, track: Track, is_active: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.track = track
        self._is_active = is_active
        self._cover_path: str | None = track.cover_path
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(12)

        # Left: Cover Artwork (44x44)
        self.cover_label = QLabel(self)
        self.cover_label.setFixedSize(44, 44)
        self.cover_label.setStyleSheet("background: transparent; background-color: transparent; border: none;")

        # Center: Title & Artist
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.title_label = MarqueeLabel(
            self.track.display_title,
            fade_width=14,
            speed_px_per_sec=28,
            alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            parent=self,
        )
        self.title_label.setFixedHeight(20)
        title_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        self.title_label.setFont(title_font)
        self.title_label.setTextColor("#ffffff")
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.title_label.setStyleSheet("background: transparent; background-color: transparent; border: none;")

        self.artist_label = MarqueeLabel(
            self.track.display_artist,
            fade_width=12,
            speed_px_per_sec=24,
            alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            parent=self,
        )
        self.artist_label.setFixedHeight(16)
        artist_font = QFont("Segoe UI", 9)
        self.artist_label.setFont(artist_font)
        self.artist_label.setTextColor("#8192a5")
        self.artist_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.artist_label.setStyleSheet("background: transparent; background-color: transparent; border: none;")

        info_layout.addWidget(self.title_label)
        info_layout.addWidget(self.artist_label)

        # Right-Center: Like Action Button (32x32)
        self.btn_like = QPushButton(self)
        self.btn_like.setFixedSize(32, 32)
        self.btn_like.setIconSize(QSize(16, 16))
        self.btn_like.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_like.clicked.connect(self._on_like_clicked)

        # Far-Right: Duration & Date/Size Metadata
        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(2)
        meta_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

        self.duration_label = QLabel(self.track.formatted_duration, self)
        self.duration_label.setStyleSheet(
            "background: transparent; background-color: transparent; border: none; font-size: 12px; font-weight: bold; color: #8192a5;"
        )

        meta_text = (
            f"{self.track.formatted_size} • {self.track.formatted_date}"
            if self.track.formatted_date
            else self.track.formatted_size
        )
        self.meta_sub_label = QLabel(meta_text, self)
        self.meta_sub_label.setStyleSheet(
            "background: transparent; background-color: transparent; border: none; font-size: 10px; color: #5d6e80;"
        )

        meta_layout.addWidget(self.duration_label)
        meta_layout.addWidget(self.meta_sub_label)

        layout.addWidget(self.cover_label)
        layout.addLayout(info_layout, stretch=1)
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
            media_album_id=self.track.media_album_id,
            file_unique_id=self.track.file_unique_id,
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
                    border-radius: 16px;
                }
                QPushButton:hover {
                    background-color: rgba(229, 57, 53, 0.18);
                }
                QPushButton:pressed {
                    background-color: rgba(229, 57, 53, 0.28);
                }
            """)
        else:
            self.btn_like.setIcon(get_svg_icon("heart_outline", "#8192a5", 16))
            tip = f"{self.tr('Like')} ({self.track.heart_count})" if self.track.heart_count > 0 else self.tr("Like")
            self.btn_like.setToolTip(tip)
            self.btn_like.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    border-radius: 16px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.12);
                }
                QPushButton:pressed {
                    background-color: rgba(255, 255, 255, 0.2);
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
                QLabel {
                    background: transparent;
                    background-color: transparent;
                    border: none;
                }
            """)
            self.title_label.setTextColor("#52a3ff")
            self.artist_label.setTextColor("#9ec6ed")
            self.duration_label.setStyleSheet("background: transparent; color: #52a3ff; font-size: 12px; font-weight: bold;")
            self.meta_sub_label.setStyleSheet("background: transparent; color: #8db3d6; font-size: 10px;")
        else:
            self.setStyleSheet("""
                TrackItemWidget {
                    background-color: transparent;
                    border: 1.5px solid transparent;
                    border-radius: 8px;
                }
                TrackItemWidget:hover {
                    background-color: #17212b;
                    border-color: #202b36;
                }
                QLabel {
                    background: transparent;
                    background-color: transparent;
                    border: none;
                }
            """)
            self.title_label.setTextColor("#ffffff")
            self.artist_label.setTextColor("#8192a5")
            self.duration_label.setStyleSheet("background: transparent; color: #8192a5; font-size: 12px; font-weight: bold;")
            self.meta_sub_label.setStyleSheet("background: transparent; color: #5d6e80; font-size: 10px;")

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
                    media_album_id=self.track.media_album_id,
                    file_unique_id=self.track.file_unique_id,
                )

        pixmap = create_rounded_cover_pixmap(
            minithumb_data=self.track.minithumbnail_data,
            cover_path=self._cover_path,
            size=44,
            is_active=self._is_active,
        )
        self.cover_label.setPixmap(pixmap)


class TrackListWidget(QListWidget):
    """List widget with robust multi-tier deduplication, safe item deletion, and instant reactivity."""

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
                padding: 1px 4px;
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
        unique_tracks: list[Track] = []
        seen_fingerprints: set[str] = set()

        for track in tracks:
            if track.fingerprint not in seen_fingerprints:
                seen_fingerprints.add(track.fingerprint)
                unique_tracks.append(track)

        self._all_tracks = unique_tracks
        self._has_more = has_more
        self._is_loading_more = False
        self._populate(self._all_tracks)

    def append_tracks(self, new_tracks: list[Track], has_more: bool = True) -> None:
        self._has_more = has_more
        self._is_loading_more = False

        existing_fps = {t.fingerprint for t in self._all_tracks}
        existing_ids = {t.id for t in self._all_tracks}

        unique_new = [
            t for t in new_tracks
            if t.fingerprint not in existing_fps and t.id not in existing_ids
        ]
        self._all_tracks.extend(unique_new)

        if not self._current_query:
            for track in unique_new:
                item = QListWidgetItem(self)
                item.setData(Qt.ItemDataRole.UserRole, track.id)
                is_active = track.id == self._active_track_id
                widget = TrackItemWidget(track, is_active=is_active)
                widget.like_clicked.connect(self.track_like_toggled.emit)
                item.setSizeHint(QSize(300, 56))
                self.addItem(item)
                self.setItemWidget(item, widget)
                self._track_widgets[track.id] = widget
        else:
            self.filter_tracks(self._current_query)

    def prepend_tracks(self, new_tracks: list[Track]) -> None:
        existing_fps = {t.fingerprint for t in self._all_tracks}
        existing_ids = {t.id for t in self._all_tracks}

        unique_new = [
            t for t in new_tracks
            if t.fingerprint not in existing_fps and t.id not in existing_ids
        ]
        if not unique_new:
            for track in new_tracks:
                self.update_track_reaction(track.chat_id, track.message_id, track.is_liked, track.heart_count)
            return

        self._all_tracks = unique_new + self._all_tracks

        if not self._current_query:
            for idx, track in enumerate(unique_new):
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, track.id)
                is_active = track.id == self._active_track_id
                widget = TrackItemWidget(track, is_active=is_active)
                widget.like_clicked.connect(self.track_like_toggled.emit)
                item.setSizeHint(QSize(300, 56))
                self.insertItem(idx, item)
                self.setItemWidget(item, widget)
                self._track_widgets[track.id] = widget
        else:
            self.filter_tracks(self._current_query)

    def remove_tracks(self, deleted_track_ids: list[str], match_fingerprint: bool = False) -> None:
        """
        Safely remove tracks by exact ID or message_id.
        match_fingerprint is ONLY True when deleting from Favorites view.
        """
        del_set = {tid for tid in deleted_track_ids if tid}
        if not del_set:
            return

        del_mids = set()
        for tid in del_set:
            parts = tid.split("_")
            if len(parts) >= 2 and parts[-1].isdigit():
                del_mids.add(int(parts[-1]))

        del_fps = set()
        if match_fingerprint:
            del_fps = {
                t.fingerprint
                for t in self._all_tracks
                if t.id in del_set or t.message_id in del_mids
            }

        # Filter internal _all_tracks collection
        self._all_tracks = [
            t for t in self._all_tracks
            if t.id not in del_set and t.message_id not in del_mids and (not match_fingerprint or t.fingerprint not in del_fps)
        ]

        # Safely remove items in reverse order to prevent index-shift glitches
        for i in reversed(range(self.count())):
            item = self.item(i)
            if not item:
                continue

            item_tid = item.data(Qt.ItemDataRole.UserRole)
            widget = self.itemWidget(item)
            widget_tid = widget.track.id if isinstance(widget, TrackItemWidget) else None
            widget_mid = widget.track.message_id if isinstance(widget, TrackItemWidget) else None
            widget_fp = widget.track.fingerprint if isinstance(widget, TrackItemWidget) else None

            should_remove = (
                item_tid in del_set
                or (widget_tid and widget_tid in del_set)
                or (widget_mid and widget_mid in del_mids)
                or (match_fingerprint and widget_fp and widget_fp in del_fps)
            )

            if should_remove:
                if item_tid:
                    self._track_widgets.pop(item_tid, None)
                if widget_tid:
                    self._track_widgets.pop(widget_tid, None)

                self.removeItemWidget(item)
                taken = self.takeItem(i)
                if widget:
                    widget.hide()
                    widget.setParent(None)
                    widget.deleteLater()
                if taken:
                    del taken

        if self._current_query:
            self.filter_tracks(self._current_query)

        self.viewport().update()

    def update_track_reaction(self, chat_id: int, message_id: int, is_liked: bool, heart_count: int) -> None:
        track_id = f"{chat_id}_{message_id}"

        # 1. Update internal state in _all_tracks
        for idx, t in enumerate(self._all_tracks):
            if t.id == track_id or t.message_id == message_id:
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
                    media_album_id=t.media_album_id,
                    file_unique_id=t.file_unique_id,
                )
                break

        # 2. Update visual widget (with fallback search by message_id)
        widget = self._track_widgets.get(track_id)
        if not widget:
            for w in self._track_widgets.values():
                if w.track.message_id == message_id or w.track.id == track_id:
                    widget = w
                    break

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
                    media_album_id=t.media_album_id,
                    file_unique_id=t.file_unique_id,
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
            item.setSizeHint(QSize(300, 56))
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