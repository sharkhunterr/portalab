"""Shared upload safety (spec 011 T007, reused by 016 attachments — F10): the content type comes from the
**magic bytes**, never from the client; only allow-listed types pass; images are decoded and re-encoded
(metadata such as EXIF/GPS stripped, decompression bombs refused); file names are sanitized."""

import io
import re
import unicodedata
import warnings
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})
DOCUMENT_TYPES = frozenset({"application/pdf", "text/plain"})
_MAGIC: tuple[tuple[bytes, int, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", 0, "image/png"),
    (b"\xff\xd8\xff", 0, "image/jpeg"),
    (b"GIF87a", 0, "image/gif"),
    (b"GIF89a", 0, "image/gif"),
    (b"%PDF-", 0, "application/pdf"),
)


class UnsafeUpload(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class CleanUpload:
    data: bytes
    content_type: str
    filename: str


def sniff(data: bytes) -> str | None:
    for magic, offset, kind in _MAGIC:
        if data[offset : offset + len(magic)] == magic:
            return kind
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if b"\x00" not in data[:4096]:
        try:
            data[:4096].decode("utf-8")
        except UnicodeDecodeError:
            return None
        return "text/plain"
    return None


def sanitize_filename(name: str, fallback: str = "file") -> str:
    base = unicodedata.normalize("NFKC", name).replace("\\", "/").rsplit("/", 1)[-1]
    base = re.sub(r"[\x00-\x1f\x7f<>:\"|?*]", "", base).strip(" .")
    return (base or fallback)[:120]


def reencode_image(data: bytes, *, max_side: int = 2048) -> tuple[bytes, str]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as probe:
                probe.verify()
            with Image.open(io.BytesIO(data)) as image:
                image.seek(0)
                has_alpha = image.mode in ("RGBA", "LA", "P")
                frame = image.convert("RGBA" if has_alpha else "RGB")
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        raise UnsafeUpload("undecodable") from exc
    except Image.DecompressionBombWarning as exc:
        raise UnsafeUpload("too_large") from exc
    frame.thumbnail((max_side, max_side))
    output = io.BytesIO()
    if has_alpha:
        frame.save(output, format="PNG", optimize=True)
        return output.getvalue(), "image/png"
    frame.save(output, format="JPEG", quality=88, optimize=True)
    return output.getvalue(), "image/jpeg"


def clean_upload(
    data: bytes,
    filename: str,
    *,
    allowed: frozenset[str] = IMAGE_TYPES,
    max_bytes: int = 10 * 1024 * 1024,
) -> CleanUpload:
    """Validate one upload: size, sniffed type in ``allowed``, images re-encoded."""
    if not data:
        raise UnsafeUpload("empty")
    if len(data) > max_bytes:
        raise UnsafeUpload("too_large")
    kind = sniff(data)
    if kind is None or kind not in allowed:
        raise UnsafeUpload("type")
    name = sanitize_filename(filename)
    if kind in IMAGE_TYPES:
        data, kind = reencode_image(data)
        stem = name.rsplit(".", 1)[0] or "image"
        name = f"{stem}.{'png' if kind == 'image/png' else 'jpg'}"
    return CleanUpload(data, kind, name)


def square_icon(data: bytes, *, side: int = 512) -> bytes:
    """Issue 159: a site's icon (tab, home screen) — re-encoded, centred on a transparent square of ``side``
    pixels (a PWA icon is square), as PNG."""
    cleaned, _ = reencode_image(data, max_side=side)
    with Image.open(io.BytesIO(cleaned)) as image:
        frame = image.convert("RGBA")
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    scale = side / max(frame.size)
    if scale > 1:  # a small image grows to fill its square
        frame = frame.resize(
            (round(frame.width * scale), round(frame.height * scale)), Image.Resampling.LANCZOS
        )
    canvas.paste(frame, ((side - frame.width) // 2, (side - frame.height) // 2), frame)
    output = io.BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return output.getvalue()
