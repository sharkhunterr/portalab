"""Issue 230: ``media.video_frames`` for Plex — still images of a title's own video file, for the cards (an
actor's character in that very film). ``ffmpeg`` reads the file Plex serves (``/library/parts/…``) with byte
ranges: it jumps to each moment and decodes one image there; nothing else is read, nothing is kept here. An
HDR video is tone-mapped (its colours would look washed out otherwise).

The server's token goes to ``ffmpeg`` as a request header; the address is the service's own (the outbound
allow-list is asked first, as for any call)."""

import asyncio
import shutil
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit

from portalab.capabilities.connector_sdk import ServiceHandle
from portalab.connectors.http_base import HttpConnector, safe_id
from portalab.core.egress import EGRESS

LONGEST = 1280  # an image's width at most
TIMEOUT = 60.0  # seconds for one image
HDR = {"smpte2084", "arib-std-b67"}
TONEMAP = (
    "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,"
    "zscale=t=bt709:m=bt709:r=tv,format=yuv420p,"
)


def part_of(item: Mapping[str, Any]) -> tuple[str, float, bool] | None:
    """The file of a title's first version: its address on the server, its length (seconds), HDR or not."""
    media = (item.get("Media") or [{}])[0]
    part = (media.get("Part") or [{}])[0]
    key = part.get("key")
    duration = item.get("duration") or media.get("duration") or part.get("duration")
    if not isinstance(key, str) or not key.startswith("/library/parts/") or not duration:
        return None
    hdr = any(
        s.get("streamType") == 1 and str(s.get("colorTrc") or "").lower() in HDR
        for s in part.get("Stream") or []
        if isinstance(s, Mapping)
    )
    return key, float(duration) / 1000, hdr


def command(url: str, token: str, second: float, *, hdr: bool) -> list[str]:
    """``ffmpeg`` taking one image at ``second``: a JPEG on its output."""
    scale = f"scale='min({LONGEST},iw)':-2"
    return [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
        "-ss", f"{second:.1f}",
        "-headers", f"X-Plex-Token: {token}\r\n",
        "-i", url,
        "-frames:v", "1", "-an", "-sn",
        "-vf", (TONEMAP if hdr else "") + scale,
        "-f", "image2", "-c:v", "mjpeg", "-q:v", "3", "pipe:1",
    ]  # fmt: skip


async def grab(argv: Sequence[str]) -> bytes | None:
    process = await asyncio.create_subprocess_exec(
        *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
    )
    try:
        out, _ = await asyncio.wait_for(process.communicate(), TIMEOUT)
    except TimeoutError:
        process.kill()
        await process.wait()
        return None
    return out if process.returncode == 0 and out[:2] == b"\xff\xd8" else None


class PlexFrames:
    def __init__(self, connector: HttpConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def frames(self, external_id: str, at: Sequence[float]) -> AsyncIterator[bytes]:
        if shutil.which("ffmpeg") is None:
            raise ConnectionError("ffmpeg is not installed")
        base = str(self.service.config.get("base_url") or "").rstrip("/")
        if not base or not EGRESS.allowed(urlsplit(base).hostname):
            raise ConnectionError("the service address is not allowed")
        document = await self.connector.get_json(self.service, f"/library/metadata/{safe_id(external_id)}")
        items = (document or {}).get("MediaContainer", {}).get("Metadata") or []
        found = part_of(items[0]) if items and isinstance(items[0], Mapping) else None
        if found is None:
            return
        key, length, hdr = found
        token = self.service.secrets.get("token", "")
        taken = failed = 0
        for fraction in at:
            image = await grab(command(base + key, token, max(0.0, min(1.0, fraction)) * length, hdr=hdr))
            if image is None:
                failed += 1
                if failed >= 3 and not taken:
                    raise ConnectionError("no image could be taken from the video")
                continue
            taken += 1
            yield image
