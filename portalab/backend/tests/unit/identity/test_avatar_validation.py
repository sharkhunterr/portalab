"""002 T037 — avatar type/size/dimension limits, metadata stripped, undecodable files rejected."""

import io

import pytest
from PIL import Image

from portalab.modules.identity.services.avatar import MAX_BYTES, OUTPUT_SIDE, InvalidAvatar, normalize_avatar

pytestmark = pytest.mark.unit


def _image(fmt: str, size: tuple[int, int] = (64, 64), **save: object) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (200, 30, 30)).save(buffer, format=fmt, **save)
    return buffer.getvalue()


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP", "GIF"])
def test_supported_formats_are_reencoded_to_png(fmt: str) -> None:
    output = normalize_avatar(_image(fmt))
    with Image.open(io.BytesIO(output)) as image:
        assert image.format == "PNG"
        assert image.size == (64, 64)


def test_large_images_are_downscaled() -> None:
    output = normalize_avatar(_image("PNG", (2000, 1000)))
    with Image.open(io.BytesIO(output)) as image:
        assert max(image.size) == OUTPUT_SIDE


def test_exif_and_text_metadata_are_stripped() -> None:
    exif = Image.Exif()
    exif[0x010E] = "secret location"  # ImageDescription
    jpeg = _image("JPEG", exif=exif.tobytes())
    assert b"secret location" in jpeg
    output = normalize_avatar(jpeg)
    assert b"secret location" not in output
    with Image.open(io.BytesIO(output)) as image:
        assert not image.getexif()
        assert "exif" not in image.info


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        (b"", "empty"),
        (b"not an image at all", "undecodable"),
        (_image("PNG")[:40], "undecodable"),
        (_image("BMP"), "format"),
        (_image("PNG", (8, 8)), "dimensions"),
        (_image("PNG", (5000, 20)), "dimensions"),
        (b"0" * (MAX_BYTES + 1), "too_large"),
    ],
)
def test_rejections(data: bytes, reason: str) -> None:
    with pytest.raises(InvalidAvatar) as caught:
        normalize_avatar(data)
    assert caught.value.code == "user.avatar_invalid"
    assert caught.value.extensions["reason"] == reason
