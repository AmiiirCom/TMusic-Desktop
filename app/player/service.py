import logging
from pathlib import Path
import shutil
import threading
from typing import Any
from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from app.config import AppConfig
from app.core.metadata import (
    AudioMetadata,
    extract_metadata_from_player,
    parse_id3v2_tags_from_bytes,
)
from app.models.track import Track
from app.network.stream_server import LocalStreamServer
from app.platform.paths import has_sufficient_disk_space, sanitize_filename
from app.settings.service import SettingsService
from app.telegram.service import TelegramService

logger = logging.getLogger("tmusic.player.service")


class PlayerService(QObject):
    """Audio playback engine with instant progressive streaming and local export."""

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
    ) -> None:
        super().__init__()
        self._config = config
        self._telegram = telegram_service
        self._settings = settings_service
        self._cache = cache_manager
        self._stream_server = stream_server

        self._sweep_lock = threading.Lock()

        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(0.8)

        self._playlist: list[Track] = []
        self._known_tracks: dict[int, Track] = {}
        self._current_index: int = -1
        self._current_track: Track | None = None
        self._current_metadata: AudioMetadata = AudioMetadata()
        self._cached_paths: dict[int, str] = {}

        self._has_prefetched_next: bool = False
        self._last_duration_ms: int = 0

        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._player.playbackRateChanged.connect(self.playback_rate_changed.emit)
        self._player.metaDataChanged.connect(self._on_media_metadata_changed)
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        self._player.errorOccurred.connect(self._on_player_error)

        self._telegram.file_download_completed.connect(self._on_file_download_completed)
        self._telegram.file_download_progress.connect(self._on_file_download_progress)

        self.sweep_and_export_internal_cache(async_mode=True)

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
            logger.info("Active track was deleted from Telegram channel. Halting playback.")
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
        return self._settings.effective_downloads_dir / clean_title

    def _find_existing_download_on_disk(self, track: Track) -> Path | None:
        """Search for the track in the downloads directory (using settings) and in the registry."""
        # Check registry (persisted)
        persisted_path = self._settings.get_downloaded_track_path(track.id, track.file_id)
        if persisted_path:
            p = Path(persisted_path)
            if p.exists() and p.stat().st_size > 0:
                return p

        # Check in-memory cache
        mem_cached = self._cached_paths.get(track.file_id)
        if mem_cached:
            p = Path(mem_cached)
            if p.exists() and p.stat().st_size > 0:
                return p

        # Scan the effective downloads directory
        downloads_dir = self._settings.effective_downloads_dir
        ext = Path(track.file_name).suffix or ".mp3"
        candidates = [
            downloads_dir / self._get_clean_download_destination(track).name,
            downloads_dir / sanitize_filename(track.file_name),
            downloads_dir / sanitize_filename(f"{track.display_title}{ext}"),
            downloads_dir / sanitize_filename(f"{track.title}{ext}"),
        ]

        for cand in candidates:
            if cand.exists() and cand.is_file() and cand.stat().st_size > 0:
                return cand

        # Fallback: if size matches, scan all files in downloads dir
        if track.size_bytes > 0 and downloads_dir.exists():
            for f in downloads_dir.glob("*"):
                if f.is_file() and f.stat().st_size == track.size_bytes:
                    return f

        return None

    def _resolve_clean_name_for_file(self, file_path: Path) -> str:
        ext = file_path.suffix or ".mp3"
        try:
            with open(file_path, "rb") as f:
                header_bytes = f.read(512 * 1024)
                meta = parse_id3v2_tags_from_bytes(header_bytes)
                if meta.title and meta.artist:
                    return sanitize_filename(f"{meta.artist} - {meta.title}{ext}")
                elif meta.title:
                    return sanitize_filename(f"{meta.title}{ext}")
        except Exception:
            pass

        return sanitize_filename(file_path.name)

    def sweep_and_export_internal_cache(self, async_mode: bool = True) -> None:
        if async_mode:
            thread = threading.Thread(
                target=self._run_sweep_worker,
                name="TMusicCacheSweeper",
                daemon=True,
            )
            thread.start()
        else:
            self._run_sweep_worker()

    def _run_sweep_worker(self) -> None:
        if not self._sweep_lock.acquire(blocking=False):
            return

        try:
            cache_dir = self._config.tdlib_files_dir
            if not cache_dir.exists():
                return

            audio_exts = (".mp3", ".flac", ".m4a", ".wav", ".aac", ".ogg", ".opus")
            for file_path in list(cache_dir.rglob("*")):
                if file_path.is_file() and file_path.suffix.lower() in audio_exts:
                    if file_path.stat().st_size == 0 or file_path.name.endswith(".temp"):
                        continue

                    clean_name = self._resolve_clean_name_for_file(file_path)
                    dest_file = self._settings.effective_downloads_dir / clean_name

                    try:
                        self._settings.effective_downloads_dir.mkdir(parents=True, exist_ok=True)
                        src_size = file_path.stat().st_size

                        if has_sufficient_disk_space(self._settings.effective_downloads_dir, src_size):
                            if not dest_file.exists() or dest_file.stat().st_size != src_size:
                                shutil.copy2(file_path, dest_file)

                            if dest_file.exists() and dest_file.stat().st_size == src_size:
                                file_path.unlink(missing_ok=True)
                                logger.debug("✨ Migrated to TMusicDownloads: %s", dest_file.name)
                    except Exception as exc:
                        logger.debug("Background sweeper error for %s: %s", file_path, exc)
        finally:
            self._sweep_lock.release()

    def play_track(self, track: Track) -> None:
        self._current_track = track
        self._known_tracks[track.file_id] = track
        self._has_prefetched_next = False
        self._current_metadata = AudioMetadata(title=track.display_title, artist=track.display_artist)
        self._update_current_index(track.id)
        self.track_changed.emit(track)
        self.metadata_updated.emit(self._current_metadata)

        existing_file = self._find_existing_download_on_disk(track)
        if existing_file:
            self._cached_paths[track.file_id] = str(existing_file)
            self._settings.register_downloaded_track(track.id, track.file_id, str(existing_file))
            self._telegram.register_downloaded_path(track.file_id, str(existing_file))
            logger.info("⚡ Instant play from local TMusicDownloads: %s", existing_file.name)
            self._start_playback_source(QUrl.fromLocalFile(str(existing_file.resolve())))
            return

        if self._stream_server:
            stream_url = self._stream_server.get_stream_url(track.file_id, size_bytes=track.size_bytes)
            logger.info("⚡ Progressive Stream starting: %s", stream_url)
            self._start_playback_source(QUrl(stream_url))
            self._telegram.download_file(track.file_id)
        else:
            self._telegram.download_file(track.file_id)

    def _start_playback_source(self, url: QUrl) -> None:
        try:
            self._player.setSource(url)
            self._player.play()
        except Exception as exc:
            logger.warning("Could not set player source (%s): %s", url, exc)

    def _switch_active_stream_to_local_file(self, local_file: Path) -> None:
        if not local_file.exists() or local_file.stat().st_size == 0:
            return

        current_url = self._player.source().toString()
        if "http://" in current_url or "127.0.0.1" in current_url:
            saved_pos = self._player.position()
            was_playing = self.is_playing
            local_url = QUrl.fromLocalFile(str(local_file.resolve()))

            logger.info("🔄 Seamless Live-to-Local Switch: %s at %d ms", local_file.name, saved_pos)

            self._player.setSource(local_url)
            if saved_pos > 0:
                self._player.setPosition(saved_pos)
            if was_playing:
                self._player.play()
                if saved_pos > 0:
                    self._player.setPosition(saved_pos)

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

        if self._find_existing_download_on_disk(next_track):
            return

        self._telegram.prefetch_audio_file(next_track.file_id)

        if next_track.cover_file_id and not next_track.cover_path:
            self._telegram.prefetch_cover_file(next_track.id, next_track.cover_file_id)

    @Slot()
    def _on_media_metadata_changed(self) -> None:
        local_path = self._cached_paths.get(self._current_track.file_id) if self._current_track else None

        header_bytes = None
        if not (local_path and Path(local_path).exists()) and self._current_track:
            header_bytes = self._telegram.get_file_header_bytes(self._current_track.file_id)

        self._current_metadata = extract_metadata_from_player(
            self._player, local_file_path=local_path, header_bytes=header_bytes
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

    @Slot(QMediaPlayer.Error, str)
    def _on_player_error(self, error: QMediaPlayer.Error, error_string: str) -> None:
        logger.warning("Media player error (%s): %s", error, error_string)
        self.error_occurred.emit(error_string)
        self.playback_state_changed.emit(False)

    @Slot(int, str)
    def _on_file_download_completed(self, file_id: int, internal_path_str: str) -> None:
        if not internal_path_str or not internal_path_str.strip():
            logger.debug("Empty path for file_id %d", file_id)
            return

        internal_path = Path(internal_path_str)

        try:
            if not internal_path.exists() or internal_path.stat().st_size == 0:
                logger.debug("File %s not available for file_id %d", internal_path, file_id)
                return
        except Exception as exc:
            logger.debug("Cannot access %s for file_id %d: %s", internal_path, file_id, exc)
            return

        # Ignore non-audio files (e.g., covers)
        if internal_path.suffix.lower() in ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'):
            return

        # Find the corresponding track
        matching_track = self._known_tracks.get(file_id)
        if not matching_track:
            if self._current_track and self._current_track.file_id == file_id:
                matching_track = self._current_track
            else:
                for t in self._playlist:
                    if t.file_id == file_id:
                        matching_track = t
                        break

        # If saving is enabled, copy to downloads directory and switch
        if self._settings.save_tracks_enabled:
            if matching_track:
                dest_file = self._get_clean_download_destination(matching_track)
                track_id = matching_track.id
            else:
                clean_name = self._resolve_clean_name_for_file(internal_path)
                dest_file = self._settings.effective_downloads_dir / clean_name
                track_id = f"0_{file_id}"

            src_size = internal_path.stat().st_size

            try:
                self._settings.effective_downloads_dir.mkdir(parents=True, exist_ok=True)

                if has_sufficient_disk_space(self._settings.effective_downloads_dir, src_size):
                    if not dest_file.exists() or dest_file.stat().st_size != src_size:
                        shutil.copy2(internal_path, dest_file)

                    if dest_file.exists() and dest_file.stat().st_size == src_size:
                        self._cached_paths[file_id] = str(dest_file)
                        self._settings.register_downloaded_track(track_id, file_id, str(dest_file))
                        self._telegram.register_downloaded_path(file_id, str(dest_file))

                        logger.info("✅ Exported to TMusicDownloads: %s", dest_file.name)

                        if self._current_track and self._current_track.file_id == file_id:
                            self._switch_active_stream_to_local_file(dest_file)

                        # Remove from TDLib cache after successful export
                        self._cache.remove_file(file_id, delete_from_tdlib=True)
                        logger.debug("🗑️ Removed cached temp file (file_id=%d)", file_id)
            except Exception as exc:
                logger.warning("Could not export to %s: %s", dest_file, exc)
                # Fallback: keep internal path
                self._cached_paths[file_id] = str(internal_path)
        else:
            # Saving disabled: just store the internal path and switch if it's the current track
            logger.debug("Saving disabled, keeping file in TDLib cache: %s", internal_path)
            self._cached_paths[file_id] = str(internal_path)
            if self._current_track and self._current_track.file_id == file_id:
                self._switch_active_stream_to_local_file(internal_path)

        # If it's the current track, refresh metadata
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
            logger.debug("Track reached end. Transitioning to next...")
            self.play_next()