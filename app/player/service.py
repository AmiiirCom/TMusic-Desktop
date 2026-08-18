import logging
from pathlib import Path
from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from app.models.track import Track
from app.telegram.service import TelegramService

logger = logging.getLogger("tmusic.player.service")


class PlayerService(QObject):
    """Core audio playback engine orchestrating QtMultimedia and TDLib downloads."""

    track_changed = Signal(Track)
    playback_state_changed = Signal(bool)
    playback_rate_changed = Signal(float)
    position_changed = Signal(int)
    duration_changed = Signal(int)
    download_progress = Signal(int, int)
    error_occurred = Signal(str)

    def __init__(self, telegram_service: TelegramService) -> None:
        super().__init__()
        self._telegram = telegram_service

        # Qt Multimedia engine
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(0.8)

        # Playlist / Queue State
        self._playlist: list[Track] = []
        self._current_index: int = -1
        self._current_track: Track | None = None
        self._pending_track: Track | None = None
        self._cached_paths: dict[int, str] = {}

        # Wire Qt Multimedia signals
        self._player.positionChanged.connect(self.position_changed.emit)
        self._player.durationChanged.connect(self.duration_changed.emit)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._player.playbackRateChanged.connect(self.playback_rate_changed.emit)
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
        self._update_current_index(track.id)
        self.track_changed.emit(track)

        cached_path = (
            self._cached_paths.get(track.file_id)
            or self._telegram.get_downloaded_path(track.file_id)
            or track.local_path
        )

        if cached_path and Path(cached_path).exists():
            self._cached_paths[track.file_id] = cached_path
            self._start_playback(cached_path)
            return

        logger.info("Track '%s' not cached. Requesting TDLib download...", track.display_title)
        self._pending_track = track
        self._telegram.download_file(track.file_id)

    def _start_playback(self, file_path: str) -> None:
        resolved_path = Path(file_path).resolve()
        logger.info("Starting audio playback: %s (Rate: %.2fx)", resolved_path, self._player.playbackRate())
        self._player.setSource(QUrl.fromLocalFile(str(resolved_path)))
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
        """Set audio playback rate (0.75, 1.0, 1.25, 1.5, 1.75)."""
        clamped_rate = max(0.5, min(2.0, rate))
        logger.info("Setting audio playback rate to: %.2fx", clamped_rate)
        self._player.setPlaybackRate(clamped_rate)
        self.playback_rate_changed.emit(clamped_rate)

    def set_muted(self, muted: bool) -> None:
        self._audio_output.setMuted(muted)

    @Slot(int, str)
    def _on_file_download_completed(self, file_id: int, local_path: str) -> None:
        self._cached_paths[file_id] = local_path
        if self._pending_track and self._pending_track.file_id == file_id:
            logger.info("Download finished for pending track: %s", self._pending_track.display_title)
            self._pending_track = None
            self._start_playback(local_path)

    @Slot(int, int, int)
    def _on_file_download_progress(self, file_id: int, downloaded: int, total: int) -> None:
        if self._pending_track and self._pending_track.file_id == file_id:
            self.download_progress.emit(downloaded, total)

    @Slot(QMediaPlayer.PlaybackState)
    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        is_playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.playback_state_changed.emit(is_playing)

    @Slot(QMediaPlayer.MediaStatus)
    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            logger.info("Track finished playing. Auto-advancing to next...")
            self.play_next()