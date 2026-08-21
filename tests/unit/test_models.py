from app.core.keywords import is_music_title
from app.core.metadata import LYRICS_KEY_REGEX
from app.models.chat import FAVORITES_CHAT_ID, OwnedChat, get_favorites_chat
from app.models.track import Track
from app.models.user import TelegramUser
from app.player.queue_manager import QueueManager


def test_track_formatting() -> None:
    """Verify track durations, sizes, fallback display titles, and reaction status."""
    track = Track(
        id="100_50",
        chat_id=100,
        message_id=50,
        file_id=999,
        title="  Yellow  ",
        artist="Coldplay",
        duration_seconds=269,  # 04:29
        size_bytes=8 * 1024 * 1024 + 500 * 1024,  # ~8.5 MB
        file_name="Coldplay_Yellow.mp3",
        is_liked=True,
        heart_count=12,
        file_unique_id="AQADAbc123Unique",
    )

    assert track.formatted_duration == "04:29"
    assert track.formatted_size == "8.5 MB"
    assert track.display_title == "Yellow"
    assert track.display_artist == "Coldplay"
    assert track.is_liked is True
    assert track.heart_count == 12
    assert track.fingerprint == "tg_uid::AQADAbc123Unique"


def test_track_fallback_title_from_filename() -> None:
    """Verify track title falls back to filename if title tag is empty."""
    track = Track(
        id="100_51",
        chat_id=100,
        message_id=51,
        file_id=1000,
        title="",
        artist="",
        duration_seconds=120,
        size_bytes=500 * 1024,
        file_name="My_Audio_Track.mp3",
    )

    assert track.display_title == "My_Audio_Track"
    assert track.display_artist == "Unknown Artist"
    assert track.formatted_size == "500.0 KB"
    assert track.is_liked is False
    assert track.heart_count == 0


def test_user_full_name() -> None:
    """Verify Telegram user name formatting."""
    user1 = TelegramUser(id=1, first_name="Amir", last_name="Zz")
    assert user1.full_name == "Amir Zz"

    user2 = TelegramUser(id=2, first_name="Amir", last_name="")
    assert user2.full_name == "Amir"


def test_owned_chat_type_display() -> None:
    """Verify channel vs group type label using default translation strings."""
    channel = OwnedChat(id=100, title="Music Channel", is_channel=True)
    assert channel.type_display == "Channel"

    group = OwnedChat(id=200, title="Music Group", is_channel=False)
    assert group.type_display == "Supergroup"


def test_music_keywords_multilingual_matching() -> None:
    """Verify multilingual support (Persian, English, Turkish, Russian, Spanish, etc.)."""
    # Persian
    assert is_music_title("کانال موزیک من") is True
    assert is_music_title("آهنگ‌های ماندگار") is True
    assert is_music_title("پلی‌لیست اختصاصی") is True
    assert is_music_title("پادکست رادیو چهرازی") is True

    # English
    assert is_music_title("My Best Music") is True
    assert is_music_title("Top 50 Playlist") is True
    assert is_music_title("Official Soundtracks") is True

    # Non-music chats
    assert is_music_title("اسناد و مدارک شرکت") is False
    assert is_music_title("گروه ترید و ارز دیجیتال") is False
    assert is_music_title("Family Backup Photos") is False


def test_lyrics_key_regex_patterns() -> None:
    """Verify that LYRICS_KEY_REGEX matches all required variations and rejects unrelated tags."""
    assert LYRICS_KEY_REGEX.match("lyrics") is not None
    assert LYRICS_KEY_REGEX.match("lyric") is not None
    assert LYRICS_KEY_REGEX.match("lyrics-eng") is not None
    assert LYRICS_KEY_REGEX.match("lyrics-xxx") is not None
    assert LYRICS_KEY_REGEX.match("unsyncedlyrics") is not None
    assert LYRICS_KEY_REGEX.match("text") is not None

    assert LYRICS_KEY_REGEX.match("title") is None
    assert LYRICS_KEY_REGEX.match("artist") is None


def test_favorites_chat_properties() -> None:
    """Verify default properties for the singleton Favorites chat."""
    fav = get_favorites_chat()
    assert fav.id == FAVORITES_CHAT_ID
    assert fav.is_favorites is True
    assert fav.type_display == "Favorites"
    assert fav.title == "Favorites"


def test_queue_manager_end_of_playlist_repeat() -> None:
    queue = QueueManager()
    t1 = Track(
        id="1_1",
        chat_id=1,
        message_id=1,
        file_id=10,
        title="Song 1",
        artist="Artist",
        duration_seconds=100,
        size_bytes=1000,
        file_name="s1.mp3",
    )
    t2 = Track(
        id="1_2",
        chat_id=1,
        message_id=2,
        file_id=20,
        title="Song 2",
        artist="Artist",
        duration_seconds=100,
        size_bytes=1000,
        file_name="s2.mp3",
    )

    queue.set_playlist([t1, t2])
    queue.set_active_track(t1)

    next_t = queue.get_next_track()
    assert next_t == t2

    repeat_t = queue.get_next_track()
    assert repeat_t == t2


def test_universal_file_unique_id_deduplication() -> None:
    """Verify that tracks with the same Telegram file_unique_id match the same fingerprint."""
    track_album_copy = Track(
        id="-1001_101",
        chat_id=-1001,
        message_id=101,
        file_id=5001,
        title="My Song",
        artist="My Artist",
        duration_seconds=200,
        size_bytes=5000000,
        file_name="song.mp3",
        media_album_id=777888,
        file_unique_id="AQADUniversalID99",
    )

    track_standalone_copy = Track(
        id="-1001_205",
        chat_id=-1001,
        message_id=205,
        file_id=5002,
        title="My Song",
        artist="My Artist",
        duration_seconds=200,
        size_bytes=5000000,
        file_name="song.mp3",
        media_album_id=0,
        file_unique_id="AQADUniversalID99",
    )

    assert track_album_copy.fingerprint == track_standalone_copy.fingerprint
    assert track_album_copy.fingerprint == "tg_uid::AQADUniversalID99"