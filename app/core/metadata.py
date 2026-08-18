from dataclasses import dataclass, field
import io
import logging
from pathlib import Path
import struct
from typing import Any
from PySide6.QtCore import QDate, QDateTime
from PySide6.QtMultimedia import QMediaMetaData, QMediaPlayer

logger = logging.getLogger("tmusic.core.metadata")


@dataclass(slots=True)
class AudioMetadata:
    """Detailed audio metadata and embedded lyrics parsed directly from audio file tags."""

    title: str = ""
    artist: str = ""
    album: str = ""
    genre: str = ""
    release_date: str = ""  # Actual music release year/date from ID3 tag
    composer: str = ""
    publisher: str = ""
    track_number: str = ""
    bitrate_kbps: int = 0
    lyrics: str = ""
    extra_tags: dict[str, str] = field(default_factory=dict)

    @property
    def has_lyrics(self) -> bool:
        return bool(self.lyrics and self.lyrics.strip())


def _decode_id3_text(frame_body: bytes) -> str:
    """Decode ID3 text frame handling UTF-8, UTF-16 with BOM, and Latin1 encodings."""
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


def parse_id3v2_tags_from_bytes(data: bytes) -> AudioMetadata:
    """
    Parse comprehensive ID3v2.3 / ID3v2.4 frames directly from audio byte header.
    Extracts Release Date, Album, Genre, Track Number, Publisher, Composer, and Lyrics.
    """
    meta = AudioMetadata()
    if len(data) < 10 or data[:3] != b"ID3":
        return meta

    try:
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

            frame_size = struct.unpack(">I", frame_size_bytes)[0]
            if frame_size <= 0 or frame_size > len(tag_data):
                break

            frame_body = stream.read(frame_size)

            # 1. Release Date / Year frames (TDRC, TYER, TDAT)
            if frame_id in ("TDRC", "TYER", "TDRL"):
                date_val = _decode_id3_text(frame_body)
                if date_val and not meta.release_date:
                    meta.release_date = date_val

            # 2. Track Title (TIT2)
            elif frame_id == "TIT2":
                meta.title = _decode_id3_text(frame_body)

            # 3. Artist (TPE1, TPE2)
            elif frame_id == "TPE1":
                meta.artist = _decode_id3_text(frame_body)

            # 4. Album (TALB)
            elif frame_id == "TALB":
                meta.album = _decode_id3_text(frame_body)

            # 5. Genre (TCON)
            elif frame_id == "TCON":
                meta.genre = _decode_id3_text(frame_body)

            # 6. Composer (TCOM)
            elif frame_id == "TCOM":
                meta.composer = _decode_id3_text(frame_body)

            # 7. Publisher / Record Label (TPUB)
            elif frame_id == "TPUB":
                meta.publisher = _decode_id3_text(frame_body)

            # 8. Track Position / Number (TRCK)
            elif frame_id == "TRCK":
                meta.track_number = _decode_id3_text(frame_body)

            # 9. Lyrics (USLT, SYLT)
            elif frame_id in ("USLT", "SYLT") and len(frame_body) > 4:
                encoding = frame_body[0]
                body = frame_body[4:]  # Skip language code
                try:
                    if encoding == 1:
                        text = body.decode("utf-16", errors="ignore")
                    elif encoding == 3:
                        text = body.decode("utf-8", errors="ignore")
                    else:
                        text = body.decode("latin1", errors="ignore")
                    if "\x00" in text:
                        text = text.split("\x00", 1)[-1]
                    if text.strip():
                        meta.lyrics = text.strip()
                except Exception:
                    pass

    except Exception as exc:
        logger.debug("ID3 byte parser exception: %s", exc)

    return meta


def extract_metadata_from_player(
    player: QMediaPlayer, local_file_path: str | None = None
) -> AudioMetadata:
    """
    Extract metadata combining FFmpeg QMediaMetaData with direct ID3 file tag parsing.
    Guarantees that actual audio file release date and lyrics take precedence.
    """
    metadata = AudioMetadata()

    # 1. Inspect direct file ID3 header from disk if file is available
    if local_file_path and Path(local_file_path).exists():
        try:
            with open(local_file_path, "rb") as f:
                header_bytes = f.read(512 * 1024)
                metadata = parse_id3v2_tags_from_bytes(header_bytes)
        except Exception as exc:
            logger.debug("Direct file tag reading error: %s", exc)

    # 2. Complement / Enhance with FFmpeg QMediaMetaData
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

        # Extract Release Date from FFmpeg metadata if not found in ID3
        if not metadata.release_date:
            date_val = meta.value(QMediaMetaData.Key.Date)
            if isinstance(date_val, QDate):
                metadata.release_date = date_val.toString("yyyy/MM/dd")
            elif isinstance(date_val, QDateTime):
                metadata.release_date = date_val.toString("yyyy/MM/dd")
            elif isinstance(date_val, (str, int)) and str(date_val).strip():
                metadata.release_date = str(date_val).strip()

        # Bitrate
        bitrate = meta.value(QMediaMetaData.Key.AudioBitRate)
        if isinstance(bitrate, (int, float)) and bitrate > 0:
            metadata.bitrate_kbps = int(bitrate) // 1000

        # Lyrics fallback from Description/Comment
        if not metadata.has_lyrics:
            comment_val = meta.stringValue(QMediaMetaData.Key.Comment) or meta.stringValue(QMediaMetaData.Key.Description)
            if comment_val and len(comment_val.strip()) > 30 and "\n" in comment_val:
                metadata.lyrics = comment_val.strip()

    return metadata