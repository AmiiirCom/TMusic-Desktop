import logging
from pathlib import Path
from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from app.core.metadata import AudioMetadata, extract_metadata_from_player
from app.models.track import Track
from app.network.stream_server import LocalStreamServer
from app.telegram.service import TelegramService

logger = logging.getLogger("tmusic.player.service")


class PlayerService(QObject):
    """
    Audio playback engine with Embedded Lyrics, Metadata extraction, and Gapless Prefetching.
    """

    track_changed = Signal(Track)
    playback_state_changed = Signal(bool)
    playback_rate_changed = Signal(float)
    position_changed = Signal(int)
    duration_changed = Signal(int)
    metadata_updated = Signal(object)  # Emits AudioMetadata
    download_progress = Signal(int, int)
    error_occurred = Signal(str)

    def __init__(
        self,
        telegram_service: TelegramService,
        stream_server: LocalStreamServer | None = None,
    ) -> None:
        super().__init__()
        self._telegram = telegram_service
        self._stream_server = stream_server

        # Qt Multimedia engine
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(0.8)

        # Playlist / Queue State
        self._playlist: list[Track] = []
        self._current_index: int = -1
        self._current_track: Track | None = None
        self._current_metadata: AudioMetadata = AudioMetadata()
        self._cached_paths: dict[int, str] = {}

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
        if start_track:
            self.play_track(start_track)
        elif self._current_track:
            self._update_current_index(self._current_track.id)

    def append_to_playlist(self, new_tracks: list[Track]) -> None:
        existing_ids = {t.id for t in self._playlist}
        unique_new = [t for t in new_tracks if t.id not in existing_ids]
        self._playlist.extend(unique_new)
        if self._current_track:
            self._update_current_index(self._current_track.id)

    def _update_current_index(self, track_id: str) -> None:
        for idx, t in enumerate(self._playlist):
            if t.id == track_id:
                self._current_index = idx
                return

    def play_track(self, track: Track) -> None:
        self._current_track = track
        self._has_prefetched_next = False
        self._current_metadata = AudioMetadata(title=track.display_title, artist=track.display_artist)
        self._update_current_index(track.id)
        self.track_changed.emit(track)
        self.metadata_updated.emit(self._current_metadata)

        cached_path = (
            self._cached_paths.get(track.file_id)
            or self._telegram.get_downloaded_path(track.file_id)
            or track.local_path
        )

        if cached_path and Path(cached_path).exists():
            self._cached_paths[track.file_id] = cached_path
            logger.info("Playing from local file cache: %s", cached_path)
            self._start_playback_source(QUrl.fromLocalFile(str(Path(cached_path).resolve())))
            return

        if self._stream_server:
            stream_url = self._stream_server.get_stream_url(track.file_id, size_bytes=track.size_bytes)
            logger.info("⚡ Instant Progressive Stream starting: %s", stream_url)
            self._start_playback_source(QUrl(stream_url))
        else:
            self._telegram.download_file(track.file_id)

    def _start_playback_source(self, url: QUrl) -> None:
        self._player.setSource(url)
        self._player.play()

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
        self._player.setPosition(position_ms)

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

        cached_path = (
            self._cached_paths.get(next_track.file_id)
            or self._telegram.get_downloaded_path(next_track.file_id)
            or next_track.local_path
        )

        if not (cached_path and Path(cached_path).exists()):
            self._telegram.prefetch_audio_file(next_track.file_id)

        if next_track.cover_file_id and not next_track.cover_path:
            self._telegram.prefetch_cover_file(next_track.id, next_track.cover_file_id)

    @Slot()
    def _on_media_metadata_changed(self) -> None:
        """Invoked when FFmpeg/Qt finishes loading ID3 metadata and lyrics."""
        local_path = self._cached_paths.get(self._current_track.file_id) if self._current_track else None
        self._current_metadata = extract_metadata_from_player(self._player, local_path)
        logger.info(
            "Metadata extracted (Album: '%s', Bitrate: %d kb/s, Has Lyrics: %s)",
            self._current_metadata.album,
            self._current_metadata.bitrate_kbps,
            self._current_metadata.has_lyrics,
        )
        self.metadata_updated.emit(self._current_metadata)

    @Slot(int)
    def _on_position_changed(self, position_ms: int) -> None:
        self.position_changed.emit(position_ms)
        self._check_smart_prefetch(position_ms, self._last_duration_ms)

    @Slot(int)
    def _on_duration_changed(self, duration_ms: int) -> None:
        self._last_duration_ms = duration_ms
        self.duration_changed.emit(duration_ms)

    @Slot(int, str)
    def _on_file_download_completed(self, file_id: int, local_path: str) -> None:
        self._cached_paths[file_id] = local_path
        logger.info("File ID %d finished downloading and saved to disk: %s", file_id, local_path)
        # Re-extract metadata with full file if needed
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
            logger.info("Track reached end. Transitioning to next...")
            self.play_next()