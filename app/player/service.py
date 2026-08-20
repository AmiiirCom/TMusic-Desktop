# app/player/service.py

from __future__ import annotations

import logging
from pathlib import Path
import shutil
from typing import TYPE_CHECKING, Any
from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from app.config import AppConfig
from app.core.metadata import AudioMetadata, extract_metadata_from_player
from app.models.track import Track
from app.platform.paths import has_sufficient_disk_space, sanitize_filename
from app.player.cache_sweeper import CacheSweeper
from app.player.prefetcher import SmartPrefetchController
from app.player.queue_manager import QueueManager

if TYPE_CHECKING:
    from app.network.stream_server import LocalStreamServer
    from app.settings.service import SettingsService
    from app.telegram.service import TelegramService

logger = logging.getLogger("tmusic.player.service")

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')


class PlayerService(QObject):
    """Core audio playback service managing QtMultimedia, progressive streams, and queue lifecycle."""

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
        settings_service: SettingsService,
        cache_manager: Any,
        stream_server: LocalStreamServer | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._telegram = telegram_service
        self._settings = settings_service
        self._cache = cache_manager
        self._stream_server = stream_server

        self._queue = QueueManager(self)
        self._sweeper = CacheSweeper(
            config=self._config,
            is_save_to_downloads_enabled=lambda: self._settings.preferences.save_to_downloads,
        )

        self._prefetcher = SmartPrefetchController(
            is_save_enabled=lambda: self._settings.preferences.save_to_downloads,
            is_playing=lambda: self.is_playing,
            get_upcoming_track=self._queue.get_upcoming_track,
            find_existing_disk=lambda t: bool(self._find_existing_download_on_disk(t)),
            prefetch_audio_callback=self._telegram.prefetch_audio_file,
            prefetch_cover_callback=self._telegram.prefetch_cover_file,
        )

        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(0.8)

        self._current_metadata = AudioMetadata()
        self._cached_paths: dict[int, str] = {}
        self._temp_streaming_file_ids: set[int] = set()
        self._last_duration_ms = 0

        self._init_signals()
        self._sweeper.start_sweep(async_mode=True)

    def _init_signals(self) -> None:
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._player.playbackRateChanged.connect(self.playback_rate_changed.emit)
        self._player.metaDataChanged.connect(self._on_media_metadata_changed)
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        self._player.errorOccurred.connect(self._on_player_error)

        self._telegram.file_download_completed.connect(self._on_file_download_completed)
        self._telegram.file_download_progress.connect(self._on_file_download_progress)

    @property
    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    @property
    def current_track(self) -> Track | None:
        return self._queue.current_track

    @property
    def current_metadata(self) -> AudioMetadata:
        return self._current_metadata

    def set_playlist(self, tracks: list[Track], start_track: Track | None = None) -> None:
        self._queue.set_playlist(tracks)
        if start_track:
            self.play_track(start_track)

    def append_to_playlist(self, new_tracks: list[Track]) -> None:
        self._queue.append_tracks(new_tracks)

    def prepend_to_playlist(self, new_tracks: list[Track]) -> None:
        self._queue.prepend_tracks(new_tracks)

    def remove_from_playlist(self, chat_id: int, deleted_track_ids: list[str]) -> None:
        if self._queue.remove_tracks(deleted_track_ids):
            self.stop()

    @Slot(str, str)
    def update_track_cover(self, track_id: str, cover_path: str) -> None:
        self._queue.update_cover(track_id, cover_path)

    @Slot(object, object, bool, int)
    def update_track_reaction(self, chat_id: int, message_id: int, is_liked: bool, heart_count: int) -> None:
        self._queue.update_reaction(chat_id, message_id, is_liked, heart_count)
        if self.current_track and self.current_track.id == f"{chat_id}_{message_id}":
            self.track_changed.emit(self.current_track)

    def stop(self) -> None:
        try:
            self._player.stop()
            self._player.setSource(QUrl())
        except Exception:
            pass

        self._cleanup_temp_stream_files(keep_file_id=None)
        self._queue.clear()
        self._current_metadata = AudioMetadata()
        self._prefetcher.reset()

        self.playback_state_changed.emit(False)
        self.position_changed.emit(0)
        self.duration_changed.emit(0)
        self.track_changed.emit(None)
        self.metadata_updated.emit(self._current_metadata)

    def play_track(self, track: Track) -> None:
        self._queue.set_active_track(track)
        self._prefetcher.reset()
        self._current_metadata = AudioMetadata(title=track.display_title, artist=track.display_artist)
        self.track_changed.emit(track)
        self.metadata_updated.emit(self._current_metadata)

        existing_file = self._find_existing_download_on_disk(track)
        if existing_file:
            self._cached_paths[track.file_id] = str(existing_file)
            self._settings.register_downloaded_track(track.id, track.file_id, str(existing_file))
            self._telegram.register_downloaded_path(track.file_id, str(existing_file))
            self._start_playback_source(QUrl.fromLocalFile(str(existing_file.resolve())))
            return

        if not self._settings.preferences.save_to_downloads:
            self._cleanup_temp_stream_files(keep_file_id=track.file_id)
            self._temp_streaming_file_ids.add(track.file_id)

        if self._stream_server:
            stream_url = self._stream_server.get_stream_url(track.file_id, size_bytes=track.size_bytes)
            self._start_playback_source(QUrl(stream_url))
            self._telegram.download_file(track.file_id)
        else:
            self._telegram.download_file(track.file_id)

    def toggle_play_pause(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        elif self._player.playbackState() == QMediaPlayer.PlaybackState.PausedState:
            self._player.play()
        elif self.current_track:
            self.play_track(self.current_track)

    def play_next(self) -> None:
        next_track = self._queue.get_next_track()
        if next_track:
            self.play_track(next_track)

    def play_previous(self) -> None:
        prev_track = self._queue.get_previous_track()
        if prev_track:
            self.play_track(prev_track)

    def seek(self, position_ms: int) -> None:
        try:
            self._player.setPosition(position_ms)
        except Exception:
            pass

    def set_volume(self, volume_percent: int) -> None:
        vol = max(0, min(100, volume_percent)) / 100.0
        self._audio_output.setVolume(vol)

    def set_playback_rate(self, rate: float) -> None:
        clamped = max(0.5, min(2.0, rate))
        self._player.setPlaybackRate(clamped)
        self.playback_rate_changed.emit(clamped)

    def _start_playback_source(self, url: QUrl) -> None:
        try:
            self._player.setSource(url)
            self._player.play()
        except Exception as exc:
            logger.warning("Could not set player source (%s): %s", url, exc)

    def _find_existing_download_on_disk(self, track: Track) -> Path | None:
        try:
            persisted = self._settings.get_downloaded_track_path(track.id, track.file_id)
            if persisted:
                p = Path(persisted)
                if p.is_file() and p.stat().st_size > 0:
                    return p

            mem_cached = self._cached_paths.get(track.file_id)
            if mem_cached:
                p = Path(mem_cached)
                if p.is_file() and p.stat().st_size > 0:
                    return p

            ext = Path(track.file_name).suffix or ".mp3"
            clean_target = self._config.downloads_dir / sanitize_filename(
                f"{track.display_artist} - {track.display_title}{ext}"
            )
            if clean_target.is_file() and clean_target.stat().st_size > 0:
                return clean_target
        except OSError:
            pass

        return None

    def _cleanup_temp_stream_files(self, keep_file_id: int | None = None) -> None:
        if self._settings.preferences.save_to_downloads:
            return

        to_remove = [fid for fid in self._temp_streaming_file_ids if fid != keep_file_id]
        for fid in to_remove:
            self._temp_streaming_file_ids.discard(fid)
            self._cached_paths.pop(fid, None)
            self._cache.remove_file(fid, delete_from_tdlib=True)

    @Slot()
    def _on_media_metadata_changed(self) -> None:
        local_path = self._cached_paths.get(self.current_track.file_id) if self.current_track else None
        header_bytes = None
        if not (local_path and Path(local_path).exists()) and self.current_track:
            header_bytes = self._telegram.get_file_header_bytes(self.current_track.file_id)

        self._current_metadata = extract_metadata_from_player(
            self._player, local_file_path=local_path, header_bytes=header_bytes
        )
        self.metadata_updated.emit(self._current_metadata)

    @Slot(int)
    def _on_position_changed(self, position_ms: int) -> None:
        self.position_changed.emit(position_ms)
        self._prefetcher.check_progress(position_ms, self._last_duration_ms)

    @Slot(int)
    def _on_duration_changed(self, duration_ms: int) -> None:
        self._last_duration_ms = duration_ms
        self.duration_changed.emit(duration_ms)

    @Slot(QMediaPlayer.Error, str)
    def _on_player_error(self, error: QMediaPlayer.Error, error_string: str) -> None:
        logger.warning("Media player error (%s): %s", error, error_string)
        self.error_occurred.emit(error_string)
        self.playback_state_changed.emit(False)

    @Slot(int, str)
    def _on_file_download_completed(self, file_id: int, internal_path_str: str) -> None:
        if not internal_path_str or not internal_path_str.strip():
            return

        internal_path = Path(internal_path_str)

        # 1. Skip image files immediately before attempting disk stats
        if internal_path.suffix.lower() in IMAGE_EXTENSIONS:
            return

        # 2. Check existence and file size safely against race conditions
        try:
            if not internal_path.is_file():
                return
            src_size = internal_path.stat().st_size
            if src_size == 0:
                return
        except OSError:
            return

        if not self._settings.preferences.save_to_downloads:
            self._temp_streaming_file_ids.add(file_id)
            if self._stream_server:
                self._stream_server.register_completed_file(file_id, str(internal_path))
            return

        matching_track = self._queue.get_track_by_file_id(file_id)
        if matching_track:
            ext = Path(matching_track.file_name).suffix or ".mp3"
            clean_name = sanitize_filename(
                f"{matching_track.display_artist} - {matching_track.display_title}{ext}"
            )
            dest_file = self._config.downloads_dir / clean_name
            track_id = matching_track.id
        else:
            clean_name = CacheSweeper.resolve_clean_filename(internal_path)
            dest_file = self._config.downloads_dir / clean_name
            track_id = f"0_{file_id}"

        try:
            self._config.downloads_dir.mkdir(parents=True, exist_ok=True)
            if has_sufficient_disk_space(self._config.downloads_dir, src_size):
                if not dest_file.exists() or dest_file.stat().st_size != src_size:
                    shutil.copy2(internal_path, dest_file)

                if dest_file.exists() and dest_file.stat().st_size == src_size:
                    self._cached_paths[file_id] = str(dest_file)
                    self._settings.register_downloaded_track(track_id, file_id, str(dest_file))
                    self._telegram.register_downloaded_path(file_id, str(dest_file))

                    if self.current_track and self.current_track.file_id == file_id:
                        self._switch_to_local_file(dest_file)

                    self._cache.remove_file(file_id, delete_from_tdlib=True)
        except Exception as exc:
            logger.warning("Could not export download to %s: %s", dest_file, exc)

    def _switch_to_local_file(self, local_file: Path) -> None:
        current_url = self._player.source().toString()
        if "http://" in current_url or "127.0.0.1" in current_url:
            pos = self._player.position()
            playing = self.is_playing
            self._player.setSource(QUrl.fromLocalFile(str(local_file.resolve())))
            if pos > 0:
                self._player.setPosition(pos)
            if playing:
                self._player.play()

    @Slot(int, int, int)
    def _on_file_download_progress(self, file_id: int, downloaded: int, total: int) -> None:
        if self.current_track and self.current_track.file_id == file_id:
            self.download_progress.emit(downloaded, total)

    @Slot(QMediaPlayer.PlaybackState)
    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        self.playback_state_changed.emit(state == QMediaPlayer.PlaybackState.PlayingState)

    @Slot(QMediaPlayer.MediaStatus)
    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.play_next()