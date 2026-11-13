"""Issue 411 — the portal's own pictures travel in the e-mail.

A picture an e-mail links on the portal (a newsletter's posters, an article's images) does not show when the
mail client cannot reach the portal: a portal on the LAN, or behind a proxy that asks to sign in first. The
pictures the portal itself serves are read from it (with the recipient's rights) and carried in the e-mail as
inline parts its HTML shows by ``cid:``; any other picture stays a link. Bounded: a few dozen pictures, a few
megabytes, only real image formats; a picture over the bounds, unreadable or refused stays a link.
"""

import asyncio
import html
import re
import secrets
from collections.abc import Sequence
from urllib.parse import urlsplit
from uuid import UUID

from portalab.capabilities.notifications import EmailImages, InlineImage
from portalab.core.logging import get_logger

log = get_logger("portalab.notifications")

MAX_IMAGES = 40
MAX_IMAGE_BYTES = 3 * 1024 * 1024
MAX_TOTAL_BYTES = 10 * 1024 * 1024
TIMEOUT = 10.0
SOURCE = re.compile(r'(<img\b[^>]*?\bsrc=")([^"]{1,2048})(")', re.IGNORECASE)
SIGNATURES = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def kind_of(data: bytes) -> str | None:
    """The picture's format from its first bytes — never from what it claims (no SVG: it can carry script)."""
    for signature, mime in SIGNATURES:
        if data.startswith(signature):
            return mime
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _path(source: str, portal: str) -> str | None:
    """The portal path a picture's address points to: a relative one, or an absolute one on the portal."""
    if source.startswith("/") and not source.startswith("//"):
        return urlsplit(source).path
    parts = urlsplit(source)
    home = urlsplit(portal)
    same = bool(home.hostname) and parts.hostname == home.hostname and parts.port == home.port
    return parts.path if parts.scheme in ("http", "https") and same else None


async def embed(
    body: str, portal: str, sources: Sequence[EmailImages], reader: UUID | None
) -> tuple[str, tuple[InlineImage, ...]]:
    """``body`` with the portal's pictures shown by ``cid:``, and those pictures."""
    if not sources or "<img" not in body.lower():
        return body, ()
    found: dict[str, InlineImage | None] = {}  # each address read once, however often it is shown
    total = 0
    for match in SOURCE.finditer(body):
        raw = match.group(2)
        if raw in found or len(found) >= MAX_IMAGES * 2:
            continue
        found[raw] = None
        path = _path(html.unescape(raw), portal)
        if path is None:
            continue
        source = next((s for s in sources if path.startswith(s.prefix)), None)
        if source is None or sum(1 for v in found.values() if v) >= MAX_IMAGES:
            continue
        try:
            data = await asyncio.wait_for(source.image(path[len(source.prefix) :], reader), TIMEOUT)
        except Exception as error:
            log.info("e-mail picture not embedded", extra={"fields": {"error": type(error).__name__}})
            continue
        mime = kind_of(data) if data else None
        if not data or mime is None or len(data) > MAX_IMAGE_BYTES or total + len(data) > MAX_TOTAL_BYTES:
            continue
        total += len(data)
        found[raw] = InlineImage(f"img{len(found)}.{secrets.token_hex(8)}@portalab", data, mime)
    images = {raw: image for raw, image in found.items() if image is not None}
    if not images:
        return body, ()

    def swap(match: re.Match[str]) -> str:
        image = images.get(match.group(2))
        return f"{match.group(1)}cid:{image.cid}{match.group(3)}" if image else match.group(0)

    return SOURCE.sub(swap, body), tuple(images.values())
