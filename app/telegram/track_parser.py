import base64
from typing import Any, Callable

from app.models.track import Track
from app.telegram.reactions import extract_heart_reaction

AUDIO_EXTENSIONS = (".mp3", ".flac", ".m4a", ".wav", ".aac", ".ogg", ".opus")


def parse_message_to_track(
    chat_id: int,
    msg: dict[str, Any],
    request_cover_callback: Callable[[str, int], None] | None = None,
    register_path_callback: Callable[[int, str], None] | None = None,
) -> Track | None:
    """Parse messageAudio or messageDocument into a domain Track instance."""
    content = msg.get("content", {})
    content_type = content.get("@type", "")
    msg_date = msg.get("date", 0)
    msg_id = msg.get("id", 0)
    track_id = f"{chat_id}_{msg_id}"

    is_liked, heart_count = extract_heart_reaction(msg)

    if content_type == "messageAudio":
        audio = content.get("audio", {})
        file_obj = audio.get("audio", {})
        local_file = file_obj.get("local", {})
        file_id = file_obj.get("id", 0)
        path = local_file.get("path", "")

        minithumb = audio.get("album_cover_minithumbnail")
        minithumb_data = (
            base64.b64decode(minithumb["data"])
            if minithumb and "data" in minithumb
            else None
        )

        hd_thumb = audio.get("album_cover_thumbnail") or audio.get("thumbnail")
        cover_file_id = 0
        cover_path = None
        if hd_thumb:
            c_file = hd_thumb.get("file", {})
            cover_file_id = c_file.get("id", 0)
            c_local = c_file.get("local", {})
            if c_local.get("is_downloading_completed") and c_local.get("path"):
                cover_path = c_local.get("path")
            elif cover_file_id > 0 and request_cover_callback:
                request_cover_callback(track_id, cover_file_id)

        if local_file.get("is_downloading_completed") and path and register_path_callback:
            register_path_callback(file_id, path)

        return Track(
            id=track_id,
            chat_id=chat_id,
            message_id=msg_id,
            file_id=file_id,
            title=audio.get("title", ""),
            artist=audio.get("performer", ""),
            duration_seconds=audio.get("duration", 0),
            size_bytes=file_obj.get("size", 0) or file_obj.get("expected_size", 0),
            file_name=audio.get("file_name", ""),
            mime_type=audio.get("mime_type", "audio/mpeg"),
            local_path=path if local_file.get("is_downloading_completed") else None,
            is_downloaded=local_file.get("is_downloading_completed", False),
            date_timestamp=msg_date,
            minithumbnail_data=minithumb_data,
            cover_file_id=cover_file_id,
            cover_path=cover_path,
            is_liked=is_liked,
            heart_count=heart_count,
        )

    elif content_type == "messageDocument":
        doc = content.get("document", {})
        file_name = doc.get("file_name", "")
        mime_type = doc.get("mime_type", "")

        if mime_type.startswith("audio/") or file_name.lower().endswith(AUDIO_EXTENSIONS):
            file_obj = doc.get("document", {})
            local_file = file_obj.get("local", {})
            file_id = file_obj.get("id", 0)
            path = local_file.get("path", "")

            minithumb = doc.get("minithumbnail")
            minithumb_data = (
                base64.b64decode(minithumb["data"])
                if minithumb and "data" in minithumb
                else None
            )

            hd_thumb = doc.get("thumbnail")
            cover_file_id = 0
            cover_path = None
            if hd_thumb:
                c_file = hd_thumb.get("file", {})
                cover_file_id = c_file.get("id", 0)
                c_local = c_file.get("local", {})
                if c_local.get("is_downloading_completed") and c_local.get("path"):
                    cover_path = c_local.get("path")
                elif cover_file_id > 0 and request_cover_callback:
                    request_cover_callback(track_id, cover_file_id)

            if local_file.get("is_downloading_completed") and path and register_path_callback:
                register_path_callback(file_id, path)

            return Track(
                id=track_id,
                chat_id=chat_id,
                message_id=msg_id,
                file_id=file_id,
                title=file_name,
                artist="Audio File",
                duration_seconds=0,
                size_bytes=file_obj.get("size", 0) or file_obj.get("expected_size", 0),
                file_name=file_name,
                mime_type=mime_type or "audio/mpeg",
                local_path=path if local_file.get("is_downloading_completed") else None,
                is_downloaded=local_file.get("is_downloading_completed", False),
                date_timestamp=msg_date,
                minithumbnail_data=minithumb_data,
                cover_file_id=cover_file_id,
                cover_path=cover_path,
                is_liked=is_liked,
                heart_count=heart_count,
            )

    return None