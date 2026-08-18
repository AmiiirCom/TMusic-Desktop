from enum import StrEnum
from functools import lru_cache
from PySide6.QtCore import QCoreApplication


def QT_TRANSLATE_NOOP(context: str, source_text: str) -> str:
    """Mark string literal for Qt Linguist / pyside6-lupdate translation extraction."""
    return source_text


class MusicKeyword(StrEnum):
    """
    Core translatable music keywords with Qt translation context.
    Recognized automatically by Qt Linguist (.ts / .qm).
    """

    MUSIC = QT_TRANSLATE_NOOP("MusicKeyword", "music")
    SONG = QT_TRANSLATE_NOOP("MusicKeyword", "song")
    TRACK = QT_TRANSLATE_NOOP("MusicKeyword", "track")
    PLAYLIST = QT_TRANSLATE_NOOP("MusicKeyword", "playlist")
    REMIX = QT_TRANSLATE_NOOP("MusicKeyword", "remix")
    PODCAST = QT_TRANSLATE_NOOP("MusicKeyword", "podcast")
    AUDIO = QT_TRANSLATE_NOOP("MusicKeyword", "audio")
    ALBUM = QT_TRANSLATE_NOOP("MusicKeyword", "album")
    SOUNDTRACK = QT_TRANSLATE_NOOP("MusicKeyword", "soundtrack")


# Built-in multilingual fallback keywords (always active across all locales)
BUILTIN_MULTILINGUAL_KEYWORDS: frozenset[str] = frozenset({
    # Persian & Arabic
    "موزیک",
    "موزيك",
    "آهنگ",
    "اهنگ",
    "موسیقی",
    "ترانه",
    "پلی لیست",
    "پلی‌لیست",
    "پلیلیست",
    "ریمیکس",
    "پادکست",
    "صدا",
    # English / International
    "music",
    "song",
    "songs",
    "track",
    "tracks",
    "playlist",
    "remix",
    "podcast",
    "audio",
    "album",
    "soundtrack",
})


def normalize_text_for_search(text: str) -> tuple[str, str]:
    """
    Normalize text for robust multi-language search (Persian, Arabic, Latin, Cyrillic).
    Returns:
        (spaced_normalized, nospaces_normalized)
    """
    if not text:
        return "", ""

    cleaned = (
        text.lower()
        .replace("\u200c", " ")  # Persian ZWNJ half-space
        .replace("ي", "ی")
        .replace("ك", "ک")
        .replace("آ", "ا")
    )
    nospaces = cleaned.replace(" ", "")
    return cleaned, nospaces


def get_active_keywords() -> set[str]:
    """
    Retrieve full set of active keywords:
    Combines built-in multilingual defaults + dynamic translations from active QTranslator.
    """
    keywords = set(BUILTIN_MULTILINGUAL_KEYWORDS)

    # Dynamically query translations from the currently active QTranslator
    for kw in MusicKeyword:
        translated = QCoreApplication.translate("MusicKeyword", kw.value)
        if translated and translated.lower() != kw.value.lower():
            keywords.add(translated.lower())

    return keywords


@lru_cache(maxsize=2048)
def is_music_title(title: str) -> bool:
    """
    Evaluate if a chat or track title matches music-related keywords.
    High performance with LRU caching and dynamic i18n support.
    """
    if not title:
        return False

    t_clean, t_nospaces = normalize_text_for_search(title)
    active_keywords = get_active_keywords()

    for kw in active_keywords:
        kw_clean, kw_nospaces = normalize_text_for_search(kw)
        if kw_clean in t_clean or kw_nospaces in t_nospaces:
            return True

    return False