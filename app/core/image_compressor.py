import logging
from pathlib import Path
from io import BytesIO
from PIL import Image

logger = logging.getLogger("tmusic.core.image_compressor")

# Constants for thumbnail compression
THUMBNAIL_SIZE = (350, 350)
JPEG_QUALITY = 70
WEBP_QUALITY = 70


def compress_image(input_path: Path, output_path: Path, max_size: tuple[int, int] = THUMBNAIL_SIZE) -> Path | None:
    """
    Compress an image to a smaller size and lower quality.
    Returns the output path if successful, None otherwise.
    """
    try:
        img = Image.open(input_path)

        # Convert to RGB if necessary (for JPEG/WebP)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Resize maintaining aspect ratio
        img.thumbnail(max_size, Image.Resampling.LANCZOS)

        # Determine output format
        suffix = output_path.suffix.lower()
        if suffix in (".jpg", ".jpeg"):
            format = "JPEG"
            kwargs = {"quality": JPEG_QUALITY, "optimize": True}
        elif suffix == ".webp":
            format = "WEBP"
            kwargs = {"quality": WEBP_QUALITY, "method": 6}
        else:
            format = "JPEG"
            kwargs = {"quality": JPEG_QUALITY, "optimize": True}
            output_path = output_path.with_suffix(".jpg")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, format=format, **kwargs)
        logger.debug("Compressed image: %s -> %s (size: %.1f KB)", input_path.name, output_path.name, output_path.stat().st_size / 1024)
        return output_path

    except Exception as exc:
        logger.warning("Failed to compress image %s: %s", input_path, exc)
        return None


def compress_image_bytes(data: bytes, output_path: Path, max_size: tuple[int, int] = THUMBNAIL_SIZE) -> Path | None:
    """Compress image from bytes to a file."""
    try:
        img = Image.open(BytesIO(data))
        return compress_image_from_pil(img, output_path, max_size)
    except Exception as exc:
        logger.warning("Failed to compress image from bytes: %s", exc)
        return None


def compress_image_from_pil(img: Image.Image, output_path: Path, max_size: tuple[int, int] = THUMBNAIL_SIZE) -> Path | None:
    """Compress a PIL Image object to a file."""
    try:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail(max_size, Image.Resampling.LANCZOS)

        suffix = output_path.suffix.lower()
        if suffix in (".jpg", ".jpeg"):
            format = "JPEG"
            kwargs = {"quality": JPEG_QUALITY, "optimize": True}
        elif suffix == ".webp":
            format = "WEBP"
            kwargs = {"quality": WEBP_QUALITY, "method": 6}
        else:
            format = "JPEG"
            kwargs = {"quality": JPEG_QUALITY, "optimize": True}
            output_path = output_path.with_suffix(".jpg")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, format=format, **kwargs)
        return output_path
    except Exception as exc:
        logger.warning("Failed to compress PIL image: %s", exc)
        return None


def get_compressed_image_path(cache_dir: Path, prefix: str, unique_id: str) -> Path:
    """Generate a consistent path for compressed images."""
    return cache_dir / f"{prefix}_{unique_id}.jpg"