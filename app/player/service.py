import logging
from pathlib import Path
import shutil
from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from app.config import AppConfig
from app.core.metadata import AudioMetadata, extract_metadata_from_player
from app.models.track import Track
from app.network.stream_server import LocalStreamServer
from app.platform.paths import has_sufficient_disk_space, sanitize_filename
from app.telegram.service import TelegramService

logger = logging.getLogger("tmusic.player.service")


class PlayerService(QObject):
    """Audio playback engine with offline playback resilience and network drop protection."""

    track_changed = Signal(object)
    playback_state_changed = Signal(bool)
    playback_rate_changed = Signal(float)
    position_changed = Signal(int)
    duration_changed = Signal(int)
    metadata_updated = Signal(object)
    download_progress = Signal(int, int)
    error_occurred = Signal(str)

    def __init__(
        self,
        config: AppConfig,
        telegram_service: TelegramService,
        stream_server: LocalStreamServer | None = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._telegram = telegram_service
        self._stream_server = stream_server

        # Qt Multimedia engine
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(0.8)

        # Playlist & Track Registry
        self._playlist: list[Track] = []
        self._known_tracks: dict[int, Track] = {}
        self._current_index: int = -1
        self._current_track: Track | None = None
        self._current_metadata: AudioMetadata = AudioMetadata()
        self._cached_paths: dict[int, str] = {}

        self._pending_temp_cleanup: dict[int, Path] = {}

        # Smart Prefetch Trackers
        self._has_prefetched_next: bool = False
        self._last_duration_ms: int = 0

        # Wire Qt Multimedia signals
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._player.playbackRateChanged.connect(self.playback_rate_changed.emit)
        self._player.metaDataChanged.connect(self._on_media_metadata_changed)
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        self._player.errorOccurred.connect(self._on_player_error)

        # Wire Telegram download signals
        self._telegram.file_download_completed.connect(self._on_file_download_completed)
        self._telegram.file_download_progress.connect(self._on_file_download_progress)

    @property
    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    @property
    def playback_rate(self) -> float:
        return self._player.playbackRate()

    @property
    def current_track(self) -> Track | None:
        return self._current_track

    @property
    def current_metadata(self) -> AudioMetadata:
        return self._current_metadata

    def set_playlist(self, tracks: list[Track], start_track: Track | None = None) -> None:
        self._playlist = list(tracks)
        for t in tracks:
            self._known_tracks[t.file_id] = t

        if start_track:
            self.play_track(start_track)
        elif self._current_track:
            self._update_current_index(self._current_track.id)

    def append_to_playlist(self, new_tracks: list[Track]) -> None:
        existing_ids = {t.id for t in self._playlist}
        unique_new = [t for t in new_tracks if t.id not in existing_ids]
        self._playlist.extend(unique_new)
        for t in unique_new:
            self._known_tracks[t.file_id] = t

        if self._current_track:
            self._update_current_index(self._current_track.id)

    def prepend_to_playlist(self, new_tracks: list[Track]) -> None:
        existing_ids = {t.id for t in self._playlist}
        unique_new = [t for t in new_tracks if t.id not in existing_ids]
        if not unique_new:
            return

        self._playlist = unique_new + self._playlist
        for t in unique_new:
            self._known_tracks[t.file_id] = t

        if self._current_track:
            self._update_current_index(self._current_track.id)

    def remove_from_playlist(self, chat_id: int, deleted_track_ids: list[str]) -> None:
        del_set = set(deleted_track_ids)
        self._playlist = [t for t in self._playlist if t.id not in del_set]

        if self._current_track and self._current_track.id in del_set:
            logger.info("Active track was deleted from Telegram. Stopping playback.")
            self.stop()
        elif self._current_track:
            self._update_current_index(self._current_track.id)

    def stop(self) -> None:
        try:
            self._player.stop()
            self._player.setSource(QUrl())
        except Exception:
            pass

        self._current_track = None
        self._current_index = -1
        self._current_metadata = AudioMetadata()
        self.playback_state_changed.emit(False)
        self.position_changed.emit(0)
        self.duration_changed.emit(0)
        self.track_changed.emit(None)
        self.metadata_updated.emit(self._current_metadata)

    def _update_current_index(self, track_id: str) -> None:
        for idx, t in enumerate(self._playlist):
            if t.id == track_id:
                self._current_index = idx
                return

    def _get_clean_download_destination(self, track: Track) -> Path:
        ext = Path(track.file_name).suffix or ".mp3"
        clean_title = sanitize_filename(f"{track.display_artist} - {track.display_title}{ext}")
        return self._config.downloads_dir / clean_title

    def _cleanup_inactive_temp_files(self) -> None:
        current_fid = self._current_track.file_id if self._current_track else 0
        to_delete = [fid for fid in self._pending_temp_cleanup if fid != current_fid]

        for fid in to_delete:
            path = self._pending_temp_cleanup.pop(fid, None)
            if path and path.exists():
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass

    def play_track(self, track: Track) -> None:
        self._current_track = track
        self._known_tracks[track.file_id] = track
        self._has_prefetched_next = False
        self._current_metadata = AudioMetadata(title=track.display_title, artist=track.display_artist)
        self._update_current_index(track.id)
        self.track_changed.emit(track)
        self.metadata_updated.emit(self._current_metadata)

        self._cleanup_inactive_temp_files()

        # 1. Offline & Cache Check: Clean TMusicDownloads
        clean_file = self._get_clean_download_destination(track)
        if clean_file.exists() and clean_file.stat().st_size > 0:
            self._cached_paths[track.file_id] = str(clean_file)
            self._telegram.register_downloaded_path(track.file_id, str(clean_file))
            logger.info("⚡ Playing offline from TMusicDownloads: %s", clean_file)
            self._start_playback_source(QUrl.fromLocalFile(str(clean_file.resolve())))
            return

        # 2. Fallback Path Check
        cached_path = self._cached_paths.get(track.file_id) or self._telegram.get_downloaded_path(track.file_id)
        if cached_path and Path(cached_path).exists() and Path(cached_path).stat().st_size > 0:
            logger.info("Playing from fallback cache: %s", cached_path)
            self._start_playback_source(QUrl.fromLocalFile(str(Path(cached_path).resolve())))
            return

        # 3. Progressive Live Streaming
        if self._stream_server:
            stream_url = self._stream_server.get_stream_url(track.file_id, size_bytes=track.size_bytes)
            logger.info("⚡ Progressive Stream starting: %s", stream_url)
            self._start_playback_source(QUrl(stream_url))
        else:
            self._telegram.download_file(track.file_id)

    def _start_playback_source(self, url: QUrl) -> None:
        try:
            self._player.setSource(url)
            self._player.play()
        except Exception as exc:
            logger.warning("Could not set player source (%s): %s", url, exc)

    def toggle_play_pause(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        elif self._player.playbackState() == QMediaPlayer.PlaybackState.PausedState:
            self._player.play()
        elif self._current_track:
            self.play_track(self._current_track)

    def play_next(self) -> None:
        if not self._playlist:
            return
        next_idx = (self._current_index + 1) % len(self._playlist)
        self._current_index = next_idx
        self.play_track(self._playlist[next_idx])

    def play_previous(self) -> None:
        if not self._playlist:
            return
        prev_idx = (self._current_index - 1 + len(self._playlist)) % len(self._playlist)
        self._current_index = prev_idx
        self.play_track(self._playlist[prev_idx])

    def seek(self, position_ms: int) -> None:
        try:
            self._player.setPosition(position_ms)
        except Exception:
            pass

    def set_volume(self, volume_percent: int) -> None:
        vol = max(0, min(100, volume_percent)) / 100.0
        self._audio_output.setVolume(vol)

    def set_playback_rate(self, rate: float) -> None:
        clamped_rate = max(0.5, min(2.0, rate))
        self._player.setPlaybackRate(clamped_rate)
        self.playback_rate_changed.emit(clamped_rate)

    def set_muted(self, muted: bool) -> None:
        self._audio_output.setMuted(muted)

    def _check_smart_prefetch(self, position_ms: int, duration_ms: int) -> None:
        if duration_ms <= 0 or self._has_prefetched_next or not self.is_playing:
            return

        progress = position_ms / duration_ms
        remaining_sec = (duration_ms - position_ms) / 1000

        if progress >= 0.70 or (duration_ms > 45_000 and remaining_sec <= 30):
            self._has_prefetched_next = True
            self._prefetch_upcoming_track()

    def _prefetch_upcoming_track(self) -> None:
        if not self._playlist or len(self._playlist) <= 1:
            return

        next_idx = (self._current_index + 1) % len(self._playlist)
        next_track = self._playlist[next_idx]

        clean_file = self._get_clean_download_destination(next_track)
        if clean_file.exists() and clean_file.stat().st_size > 0:
            return

        cached_path = self._cached_paths.get(next_track.file_id) or self._telegram.get_downloaded_path(next_track.file_id)
        if not (cached_path and Path(cached_path).exists()):
            self._telegram.prefetch_audio_file(next_track.file_id)

        if next_track.cover_file_id and not next_track.cover_path:
            self._telegram.prefetch_cover_file(next_track.id, next_track.cover_file_id)

    @Slot()
    def _on_media_metadata_changed(self) -> None:
        local_path = self._cached_paths.get(self._current_track.file_id) if self._current_track else None
        self._current_metadata = extract_metadata_from_player(self._player, local_path)
        self.metadata_updated.emit(self._current_metadata)

    @Slot(int)
    def _on_position_changed(self, position_ms: int) -> None:
        self.position_changed.emit(position_ms)
        self._check_smart_prefetch(position_ms, self._last_duration_ms)

    @Slot(int)
    def _on_duration_changed(self, duration_ms: int) -> None:
        self._last_duration_ms = duration_ms
        self.duration_changed.emit(duration_ms)

    @Slot(QMediaPlayer.Error, str)
    def _on_player_error(self, error: QMediaPlayer.Error, error_string: str) -> None:
        """Handle media player network drop or decode errors gracefully."""
        logger.warning("Media player encountered error (%s): %s", error, error_string)
        self.error_occurred.emit(error_string)
        self.playback_state_changed.emit(False)

    @Slot(int, str)
    def _on_file_download_completed(self, file_id: int, internal_path_str: str) -> None:
        internal_path = Path(internal_path_str)

        matching_track = self._known_tracks.get(file_id)
        if not matching_track:
            if self._current_track and self._current_track.file_id == file_id:
                matching_track = self._current_track
            else:
                for t in self._playlist:
                    if t.file_id == file_id:
                        matching_track = t
                        break

        if matching_track and internal_path.exists():
            dest_file = self._get_clean_download_destination(matching_track)
            src_size = internal_path.stat().st_size

            try:
                self._config.downloads_dir.mkdir(parents=True, exist_ok=True)

                if has_sufficient_disk_space(self._config.downloads_dir, matching_track.size_bytes):
                    if not dest_file.exists() or dest_file.stat().st_size != src_size:
                        shutil.copy2(internal_path, dest_file)

                    if dest_file.exists() and dest_file.stat().st_size == src_size:
                        self._cached_paths[file_id] = str(dest_file)
                        self._telegram.register_downloaded_path(file_id, str(dest_file))

                        if self._stream_server:
                            self._stream_server.register_completed_file(file_id, str(dest_file))

                        logger.info("✅ Exported to TMusicDownloads: %s", dest_file.name)
                        self._pending_temp_cleanup[file_id] = internal_path

            except Exception as exc:
                logger.warning("Could not export audio to %s: %s", dest_file, exc)
                self._cached_paths[file_id] = str(internal_path)
                self._telegram.register_downloaded_path(file_id, str(internal_path))

        if self._current_track and self._current_track.file_id == file_id:
            self._on_media_metadata_changed()

    @Slot(int, int, int)
    def _on_file_download_progress(self, file_id: int, downloaded: int, total: int) -> None:
        if self._current_track and self._current_track.file_id == file_id:
            self.download_progress.emit(downloaded, total)

    @Slot(QMediaPlayer.PlaybackState)
    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        is_playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.playback_state_changed.emit(is_playing)

    @Slot(QMediaPlayer.MediaStatus)
    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            logger.info("Track reached end. Purging temp cache and advancing to next...")
            self._cleanup_inactive_temp_files()
            self.play_next()