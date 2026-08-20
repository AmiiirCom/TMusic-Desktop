# app/player/prefetcher.py

import logging
from typing import Callable

from app.models.track import Track

logger = logging.getLogger("tmusic.player.prefetcher")


class SmartPrefetchController:
    """
    Monitors active playback progress and triggers asynchronous background
    prefetching for the upcoming track when playback crosses defined thresholds.
    """

    def __init__(
        self,
        is_save_enabled: Callable[[], bool],
        is_playing: Callable[[], bool],
        get_upcoming_track: Callable[[], Track | None],
        find_existing_disk: Callable[[Track], bool],
        prefetch_audio_callback: Callable[[int], None],
        prefetch_cover_callback: Callable[[str, int], None],
    ) -> None:
        self._is_save_enabled = is_save_enabled
        self._is_playing = is_playing
        self._get_upcoming_track = get_upcoming_track
        self._find_existing_disk = find_existing_disk
        self._prefetch_audio = prefetch_audio_callback
        self._prefetch_cover = prefetch_cover_callback
        self._has_prefetched = False

    def reset(self) -> None:
        """Reset the prefetch trigger state when a new track begins playing."""
        self._has_prefetched = False

    def check_progress(self, position_ms: int, duration_ms: int) -> None:
        """
        Evaluate current playback metrics and start prefetching if thresholds are met.
        Triggers when:
        - 70% or more of the track has been played, OR
        - Remaining playback time is 30 seconds or less (for tracks > 45s).
        """
        if duration_ms <= 0 or self._has_prefetched or not self._is_playing():
            return

        if not self._is_save_enabled():
            return

        progress = position_ms / duration_ms
        remaining_sec = (duration_ms - position_ms) / 1000

        if progress >= 0.70 or (duration_ms > 45_000 and remaining_sec <= 30):
            self._has_prefetched = True
            next_track = self._get_upcoming_track()

            if next_track and not self._find_existing_disk(next_track):
                logger.debug(
                    "Smart prefetching next track '%s' (ID: %d)",
                    next_track.display_title,
                    next_track.file_id,
                )
                self._prefetch_audio(next_track.file_id)

                if next_track.cover_file_id and not next_track.cover_path:
                    self._prefetch_cover(next_track.id, next_track.cover_file_id)