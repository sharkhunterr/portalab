"""Avatar validation and normalization (research R12, FR-011).

Uploads are decoded with Pillow, size/dimension-checked and **re-encoded** to PNG (≤ 512 px), which strips
every metadata block (EXIF/GPS, comments, ICC). Undecodable files, decompression bombs, animations beyond the
first frame and unsupported formats are refused with ``user.avatar_invalid``.
"""

import io
import warnings

from PIL import Image, UnidentifiedImageError

from portalab.core.errors import ValidationFailed

MAX_BYTES = 2 * 1024 * 1024
MIN_SIDE = 16
MAX_SIDE = 4096
OUTPUT_SIDE = 512
ALLOWED_FORMATS = frozenset({"PNG", "JPEG", "WEBP", "GIF"})
OUTPUT_CONTENT_TYPE = "image/png"


class InvalidAvatar(ValidationFailed):
    default_code = "user.avatar_invalid"
    default_title = "Invalid avatar image"


def normalize_avatar(data: bytes) -> bytes:
    if not data:
        raise InvalidAvatar("The image is empty.", extensions={"reason": "empty"})
    if len(data) > MAX_BYTES:
        raise InvalidAvatar("The image is larger than 2 MiB.", extensions={"reason": "too_large"})
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as probe:
                image_format = probe.format
                width, height = probe.size
                probe.verify()
            if image_format not in ALLOWED_FORMATS:
                raise InvalidAvatar("Use a PNG, JPEG, WebP or GIF image.", extensions={"reason": "format"})
            if not (MIN_SIDE <= width <= MAX_SIDE and MIN_SIDE <= height <= MAX_SIDE):
                raise InvalidAvatar(
                    f"Images must be between {MIN_SIDE} and {MAX_SIDE} pixels per side.",
                    extensions={"reason": "dimensions"},
                )
            with Image.open(io.BytesIO(data)) as image:
                image.seek(0)
                frame = image.convert("RGBA")
    except InvalidAvatar:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise InvalidAvatar(
            "The file is not a readable image.", extensions={"reason": "undecodable"}
        ) from exc
    frame.thumbnail((OUTPUT_SIDE, OUTPUT_SIDE))
    output = io.BytesIO()
    frame.save(output, format="PNG", optimize=True)  # fresh file: no EXIF, no text chunks
    return output.getvalue()
