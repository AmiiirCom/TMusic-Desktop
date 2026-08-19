from dataclasses import dataclass, field
import io
import logging
from pathlib import Path
import re
import struct
from typing import Any
from PySide6.QtCore import QDate, QDateTime
from PySide6.QtMultimedia import QMediaMetaData, QMediaPlayer

logger = logging.getLogger("tmusic.core.metadata")

# Strict Regex pattern for lyric, lyrics, lyric-*, lyrics-*, unsyncedlyrics, text
LYRICS_KEY_REGEX = re.compile(
    r"^(lyrics?(-[a-zA-Z0-9_]+)?|unsynced[_\s]?lyrics?|text)$",
    re.IGNORECASE,
)


@dataclass(slots=True)
class AudioMetadata:
    """Detailed audio metadata and embedded lyrics parsed directly from audio tags."""

    title: str = ""
    artist: str = ""
    album: str = ""
    genre: str = ""
    release_date: str = ""
    composer: str = ""
    publisher: str = ""
    track_number: str = ""
    bitrate_kbps: int = 0
    lyrics: str = ""
    extra_tags: dict[str, str] = field(default_factory=dict)

    @property
    def has_lyrics(self) -> bool:
        return bool(self.lyrics and self.lyrics.strip())


def _clean_lyrics_text(raw_text: str) -> str:
    """Clean descriptors, BOM artifacts (like 'Ă'), and extract genuine lyrics."""
    if not raw_text:
        return ""

    clean = (
        raw_text.replace("\ufeff", "")
        .replace("\ufffe", "")
        .replace("\x00", "")
        .strip()
    )

    descriptor_prefixes = (
        "async lyric song",
        "sync lyric song",
        "lyrics-xxx",
        "lyrics-eng",
        "unsynced lyrics",
        "unsyncedlyrics",
        "lyrics",
        "lyric",
    )

    clean_lower = clean.lower()
    for prefix in descriptor_prefixes:
        if clean_lower.startswith(prefix):
            clean = clean[len(prefix) :].strip()
            clean_lower = clean.lower()

    return clean.strip()


def _decode_id3_text(frame_body: bytes) -> str:
    """Decode standard ID3 text frame."""
    if not frame_body:
        return ""
    encoding = frame_body[0]
    raw = frame_body[1:]
    try:
        if encoding == 1:
            text = raw.decode("utf-16", errors="ignore")
        elif encoding == 2:
            text = raw.decode("utf-16-be", errors="ignore")
        elif encoding == 3:
            text = raw.decode("utf-8", errors="ignore")
        else:
            text = raw.decode("latin1", errors="ignore")
        return text.replace("\x00", "").strip()
    except Exception:
        return ""


def _parse_uslt_frame(frame_body: bytes) -> str:
    """
    Parse USLT / SYLT lyrics frame accurately separating descriptor from lyrics text
    across all encodings and language codes.
    """
    if len(frame_body) < 4:
        return ""

    encoding = frame_body[0]
    payload = frame_body[4:]

    try:
        if encoding == 1:
            decoded_str = payload.decode("utf-16", errors="ignore")
        elif encoding == 2:
            decoded_str = payload.decode("utf-16-be", errors="ignore")
        elif encoding == 3:
            decoded_str = payload.decode("utf-8", errors="ignore")
        else:
            try:
                decoded_str = payload.decode("utf-8")
            except UnicodeDecodeError:
                decoded_str = payload.decode("latin1", errors="ignore")

        if "\x00" in decoded_str:
            parts = decoded_str.split("\x00")
            candidates = [p.strip() for p in parts if p.strip()]
            if candidates:
                multiline = [c for c in candidates if "\n" in c or len(c) > 40]
                lyrics_raw = multiline[0] if multiline else candidates[-1]
            else:
                lyrics_raw = decoded_str
        else:
            lyrics_raw = decoded_str

        return _clean_lyrics_text(lyrics_raw)
    except Exception as exc:
        logger.debug("Error parsing USLT frame: %s", exc)
        return ""


def _parse_txxx_frame(frame_body: bytes) -> tuple[str, str]:
    """Parse TXXX user-defined frame: returns (description, value)."""
    if len(frame_body) < 2:
        return "", ""

    encoding = frame_body[0]
    payload = frame_body[1:]

    try:
        if encoding in (1, 2):
            enc_name = "utf-16" if encoding == 1 else "utf-16-be"
            decoded = payload.decode(enc_name, errors="ignore")
        else:
            enc_name = "utf-8" if encoding == 3 else "latin1"
            decoded = payload.decode(enc_name, errors="ignore")

        if "\x00" in decoded:
            parts = decoded.split("\x00", 1)
            desc = parts[0].strip()
            val = parts[1].strip() if len(parts) > 1 else ""
        else:
            desc = ""
            val = decoded.strip()

        return desc, val
    except Exception:
        return "", ""


def _scan_raw_uslt_fallback(data: bytes) -> str:
    """Direct signature scanner finding USLT frames in headers."""
    pos = 0
    while True:
        pos = data.find(b"USLT", pos)
        if pos == -1 or pos + 10 >= len(data):
            break

        size_bytes = data[pos + 4 : pos + 8]
        size_std = struct.unpack(">I", size_bytes)[0]
        size_sync = (
            (size_bytes[0] << 21)
            | (size_bytes[1] << 14)
            | (size_bytes[2] << 7)
            | size_bytes[3]
        )

        for sz in (size_std, size_sync):
            if 4 < sz <= len(data) - (pos + 10):
                body = data[pos + 10 : pos + 10 + sz]
                lyrics = _parse_uslt_frame(body)
                if lyrics and len(lyrics) > 20:
                    return lyrics

        pos += 4

    return ""


def parse_id3v2_tags_from_bytes(data: bytes) -> AudioMetadata:
    """Parse ID3v2 frames with version-aware sizes and clean lyrics extraction."""
    meta = AudioMetadata()
    if len(data) < 10 or data[:3] != b"ID3":
        return meta

    try:
        version_major = data[3]
        size_bytes = data[6:10]
        tag_size = (
            (size_bytes[0] << 21)
            | (size_bytes[1] << 14)
            | (size_bytes[2] << 7)
            | size_bytes[3]
        )
        tag_data = data[10 : min(len(data), 10 + tag_size)]
        stream = io.BytesIO(tag_data)

        while stream.tell() < len(tag_data) - 10:
            frame_id_bytes = stream.read(4)
            if len(frame_id_bytes) < 4 or frame_id_bytes[0] == 0:
                break

            frame_id = frame_id_bytes.decode("latin1", errors="ignore")
            frame_size_bytes = stream.read(4)
            _flags = stream.read(2)

            if len(frame_size_bytes) < 4:
                break

            if version_major == 4:
                frame_size = (
                    (frame_size_bytes[0] << 21)
                    | (frame_size_bytes[1] << 14)
                    | (frame_size_bytes[2] << 7)
                    | frame_size_bytes[3]
                )
            else:
                frame_size = struct.unpack(">I", frame_size_bytes)[0]

            if frame_size <= 0 or frame_size > len(tag_data) - stream.tell():
                break

            frame_body = stream.read(frame_size)

            # Metadata Fields
            if frame_id in ("TDRC", "TYER", "TDRL"):
                date_val = _decode_id3_text(frame_body)
                if date_val and not meta.release_date:
                    meta.release_date = date_val
            elif frame_id == "TIT2":
                meta.title = _decode_id3_text(frame_body)
            elif frame_id in ("TPE1", "TPE2") and not meta.artist:
                meta.artist = _decode_id3_text(frame_body)
            elif frame_id == "TALB":
                meta.album = _decode_id3_text(frame_body)
            elif frame_id == "TCON":
                meta.genre = _decode_id3_text(frame_body)
            elif frame_id == "TCOM":
                meta.composer = _decode_id3_text(frame_body)
            elif frame_id == "TPUB":
                meta.publisher = _decode_id3_text(frame_body)
            elif frame_id == "TRCK":
                meta.track_number = _decode_id3_text(frame_body)

            # --- Strict Lyrics Extraction ---
            elif frame_id in ("USLT", "SYLT", "ULT"):
                lyrics_text = _parse_uslt_frame(frame_body)
                if lyrics_text and len(lyrics_text) > 15:
                    meta.lyrics = lyrics_text

            elif frame_id == "TXXX":
                desc, val = _parse_txxx_frame(frame_body)
                if LYRICS_KEY_REGEX.match(desc.strip()) and val.strip():
                    clean_val = _clean_lyrics_text(val)
                    if clean_val and len(clean_val) > 15:
                        meta.lyrics = clean_val

    except Exception as exc:
        logger.debug("ID3 structured parser exception: %s", exc)

    if not meta.has_lyrics:
        raw_lyrics = _scan_raw_uslt_fallback(data)
        if raw_lyrics:
            meta.lyrics = raw_lyrics

    return meta


def extract_metadata_from_player(
    player: QMediaPlayer,
    local_file_path: str | None = None,
    header_bytes: bytes | None = None,
) -> AudioMetadata:
    """
    Extract metadata prioritizing exact clean lyrics.
    Inspects up to 4MB of header bytes or local file directly.
    """
    metadata = AudioMetadata()

    bytes_to_parse: bytes | None = None
    if local_file_path and Path(local_file_path).exists():
        try:
            with open(local_file_path, "rb") as f:
                bytes_to_parse = f.read(4 * 1024 * 1024)
        except Exception:
            pass
    elif header_bytes:
        bytes_to_parse = header_bytes

    if bytes_to_parse:
        metadata = parse_id3v2_tags_from_bytes(bytes_to_parse)

    meta = player.metaData()
    if not meta.isEmpty():
        if not metadata.title:
            metadata.title = meta.stringValue(QMediaMetaData.Key.Title) or ""
        if not metadata.artist:
            metadata.artist = (
                meta.stringValue(QMediaMetaData.Key.Author)
                or meta.stringValue(QMediaMetaData.Key.ContributingArtist)
                or meta.stringValue(QMediaMetaData.Key.AlbumArtist)
                or ""
            )
        if not metadata.album:
            metadata.album = meta.stringValue(QMediaMetaData.Key.AlbumTitle) or ""
        if not metadata.genre:
            metadata.genre = meta.stringValue(QMediaMetaData.Key.Genre) or ""
        if not metadata.composer:
            metadata.composer = meta.stringValue(QMediaMetaData.Key.Composer) or ""
        if not metadata.publisher:
            metadata.publisher = meta.stringValue(QMediaMetaData.Key.Publisher) or ""

        if not metadata.release_date:
            date_val = meta.value(QMediaMetaData.Key.Date)
            if isinstance(date_val, (QDate, QDateTime)):
                metadata.release_date = date_val.toString("yyyy/MM/dd")
            elif isinstance(date_val, (str, int)) and str(date_val).strip():
                metadata.release_date = str(date_val).strip()

        bitrate = meta.value(QMediaMetaData.Key.AudioBitRate)
        if isinstance(bitrate, (int, float)) and bitrate > 0:
            metadata.bitrate_kbps = int(bitrate) // 1000

        if not metadata.has_lyrics:
            for key in meta.keys():
                key_name = str(key).strip().lower()
                if "." in key_name:
                    key_name = key_name.split(".")[-1]

                if LYRICS_KEY_REGEX.match(key_name):
                    val = meta.value(key)
                    if isinstance(val, str) and val.strip():
                        clean_l = _clean_lyrics_text(val)
                        if clean_l and len(clean_l) > 15:
                            metadata.lyrics = clean_l
                            break

    return metadata