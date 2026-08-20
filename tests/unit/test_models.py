from app.models.track import Track
from app.models.chat import OwnedChat
from app.models.user import TelegramUser
from app.core.keywords import MusicKeyword, is_music_title
from app.core.metadata import LYRICS_KEY_REGEX


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
    )

    assert track.formatted_duration == "04:29"
    assert track.formatted_size == "8.5 MB"
    assert track.display_title == "Yellow"
    assert track.display_artist == "Coldplay"
    assert track.is_liked is True
    assert track.heart_count == 12


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
        size_bytes=500 * 1024,  # 500 KB
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
    """Verify channel vs group type label."""
    channel = OwnedChat(id=100, title="Music Channel", is_channel=True)
    assert channel.type_display == "کانال"

    group = OwnedChat(id=200, title="Music Group", is_channel=False)
    assert group.type_display == "سوپرگروه"


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
    # Positive matches
    assert LYRICS_KEY_REGEX.match("lyrics") is not None
    assert LYRICS_KEY_REGEX.match("lyric") is not None
    assert LYRICS_KEY_REGEX.match("lyrics-eng") is not None
    assert LYRICS_KEY_REGEX.match("lyrics-xxx") is not None
    assert LYRICS_KEY_REGEX.match("lyric-eng") is not None
    assert LYRICS_KEY_REGEX.match("lyrics-fas") is not None
    assert LYRICS_KEY_REGEX.match("lyrics-fra") is not None
    assert LYRICS_KEY_REGEX.match("lyrics-deu") is not None
    assert LYRICS_KEY_REGEX.match("lyric-custom_language") is not None
    assert LYRICS_KEY_REGEX.match("unsyncedlyrics") is not None
    assert LYRICS_KEY_REGEX.match("unsynced_lyrics") is not None
    assert LYRICS_KEY_REGEX.match("unsynced lyrics") is not None
    assert LYRICS_KEY_REGEX.match("text") is not None

    # Negative non-lyrics matches
    assert LYRICS_KEY_REGEX.match("title") is None
    assert LYRICS_KEY_REGEX.match("artist") is None
    assert LYRICS_KEY_REGEX.match("album") is None
    assert LYRICS_KEY_REGEX.match("comment") is None