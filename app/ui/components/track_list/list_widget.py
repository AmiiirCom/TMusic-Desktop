from typing import Any
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem, QWidget

from app.models.track import Track
from app.ui.components.track_list.item_widget import TrackItemWidget


class TrackListWidget(QListWidget):
    """List widget managing track items, scroll pagination, and live updates."""

    track_selected = Signal(Track)
    track_like_toggled = Signal(Track)
    load_more_requested = Signal()
    search_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
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
        """)

        self.itemClicked.connect(self._on_item_clicked)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            event.ignore()
            return
        super().mousePressEvent(event)

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
            if widget:
                for i in range(self.count()):
                    item = self.item(i)
                    if self.itemWidget(item) == widget:
                        self.takeItem(i)
                        break

    def update_track_reaction(self, chat_id: int, message_id: int, is_liked: bool, heart_count: int) -> None:
        track_id = f"{chat_id}_{message_id}"
        widget = self._track_widgets.get(track_id)
        if widget:
            widget.update_reaction(is_liked, heart_count)

    def update_track_cover(self, track_id: str, cover_path: str) -> None:
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
                t for t in self._all_tracks
                if self._current_query in t.display_title.lower()
                or self._current_query in t.display_artist.lower()
            ]
            self._populate(filtered)
        self.search_requested.emit(query.strip())

    def scroll_to_track(self, track_id: str) -> None:
        if track_id not in self._track_widgets:
            return
        widget = self._track_widgets[track_id]
        for i in range(self.count()):
            item = self.item(i)
            if self.itemWidget(item) == widget:
                self.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
                break

    def _populate(self, tracks: list[Track]) -> None:
        self.clear()
        self._track_widgets.clear()
        for track in tracks:
            item = QListWidgetItem(self)
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