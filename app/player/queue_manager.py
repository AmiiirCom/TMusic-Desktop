from typing import Any
from PySide6.QtCore import QObject, Signal

from app.models.track import Track


class QueueManager(QObject):
    """Manages playlist queue, sequential track navigation with end-of-list repeat, and reactions."""

    playlist_updated = Signal(list)
    track_changed = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._playlist: list[Track] = []
        self._known_tracks: dict[int, Track] = {}
        self._current_index: int = -1
        self._current_track: Track | None = None

    @property
    def playlist(self) -> list[Track]:
        return self._playlist

    @property
    def current_track(self) -> Track | None:
        return self._current_track

    @property
    def current_index(self) -> int:
        return self._current_index

    def get_track_by_file_id(self, file_id: int) -> Track | None:
        return self._known_tracks.get(file_id)

    def set_playlist(self, tracks: list[Track]) -> None:
        unique: list[Track] = []
        seen_fps: set[str] = set()
        for t in tracks:
            if t.fingerprint not in seen_fps:
                seen_fps.add(t.fingerprint)
                unique.append(t)

        self._playlist = list(unique)
        for t in unique:
            self._known_tracks[t.file_id] = t
        if self._current_track:
            self._sync_index(self._current_track.id)

    def append_tracks(self, tracks: list[Track]) -> None:
        existing_fps = {t.fingerprint for t in self._playlist}
        existing_ids = {t.id for t in self._playlist}
        unique = [t for t in tracks if t.fingerprint not in existing_fps and t.id not in existing_ids]
        self._playlist.extend(unique)
        for t in unique:
            self._known_tracks[t.file_id] = t
        if self._current_track:
            self._sync_index(self._current_track.id)

    def prepend_tracks(self, tracks: list[Track]) -> None:
        existing_fps = {t.fingerprint for t in self._playlist}
        existing_ids = {t.id for t in self._playlist}
        unique = [t for t in tracks if t.fingerprint not in existing_fps and t.id not in existing_ids]
        if not unique:
            return
        self._playlist = unique + self._playlist
        for t in unique:
            self._known_tracks[t.file_id] = t
        if self._current_track:
            self._sync_index(self._current_track.id)

    def remove_tracks(self, deleted_ids: list[str]) -> bool:
        del_set = set(deleted_ids)
        self._playlist = [t for t in self._playlist if t.id not in del_set]

        current_deleted = False
        if self._current_track and self._current_track.id in del_set:
            current_deleted = True
            self._current_track = None
            self._current_index = -1
        elif self._current_track:
            self._sync_index(self._current_track.id)

        return current_deleted

    def set_active_track(self, track: Track) -> None:
        self._current_track = track
        self._known_tracks[track.file_id] = track
        self._sync_index(track.id)

    def get_next_track(self) -> Track | None:
        """
        Advance to the next track sequentially.
        If at the end of the playlist, repeat the current/last track.
        """
        if not self._playlist:
            return None

        if self._current_index + 1 < len(self._playlist):
            self._current_index += 1
            return self._playlist[self._current_index]
        else:
            if 0 <= self._current_index < len(self._playlist):
                return self._playlist[self._current_index]
            return self._playlist[-1]

    def get_previous_track(self) -> Track | None:
        """Move to the previous track sequentially."""
        if not self._playlist:
            return None

        if self._current_index - 1 >= 0:
            self._current_index -= 1
            return self._playlist[self._current_index]
        else:
            return self._playlist[0]

    def get_upcoming_track(self) -> Track | None:
        if not self._playlist or len(self._playlist) <= 1:
            return None
        if self._current_index + 1 < len(self._playlist):
            return self._playlist[self._current_index + 1]
        return None

    def update_cover(self, track_id: str, cover_path: str) -> None:
        for idx, t in enumerate(self._playlist):
            if t.id == track_id:
                updated = self._clone_track(t, cover_path=cover_path)
                self._playlist[idx] = updated
                self._known_tracks[t.file_id] = updated
                if self._current_track and self._current_track.id == track_id:
                    self._current_track = updated
                break

    def update_reaction(self, chat_id: int, message_id: int, is_liked: bool, heart_count: int) -> None:
        track_id = f"{chat_id}_{message_id}"
        for idx, t in enumerate(self._playlist):
            if t.id == track_id or (t.chat_id == chat_id and t.message_id == message_id):
                updated = self._clone_track(t, is_liked=is_liked, heart_count=heart_count)
                self._playlist[idx] = updated
                self._known_tracks[t.file_id] = updated
                if self._current_track and (
                    self._current_track.id == track_id
                    or (self._current_track.chat_id == chat_id and self._current_track.message_id == message_id)
                ):
                    self._current_track = updated
                break

    def clear(self) -> None:
        self._current_track = None
        self._current_index = -1

    def _sync_index(self, track_id: str) -> None:
        for idx, t in enumerate(self._playlist):
            if t.id == track_id:
                self._current_index = idx
                return

    @staticmethod
    def _clone_track(t: Track, **kwargs: Any) -> Track:
        data = {
            "id": t.id,
            "chat_id": t.chat_id,
            "message_id": t.message_id,
            "file_id": t.file_id,
            "title": t.title,
            "artist": t.artist,
            "duration_seconds": t.duration_seconds,
            "size_bytes": t.size_bytes,
            "file_name": t.file_name,
            "mime_type": t.mime_type,
            "local_path": t.local_path,
            "is_downloaded": t.is_downloaded,
            "date_timestamp": t.date_timestamp,
            "minithumbnail_data": t.minithumbnail_data,
            "cover_file_id": t.cover_file_id,
            "cover_path": t.cover_path,
            "is_liked": t.is_liked,
            "heart_count": t.heart_count,
            "media_album_id": t.media_album_id,
            "file_unique_id": t.file_unique_id,
        }
        data.update(kwargs)
        return Track(**data)