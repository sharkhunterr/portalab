"""``searxng`` connector (issue 229): a self-hosted SearXNG — a metasearch engine asking Bing, Brave, Google
and others for images, with no key and no account (its JSON format must be enabled in its ``settings.yml``).

* ``media.image_search``: the images it finds for a query (where each is, its page's title, its size, the
  engine), and fetching one — the cards look for an actor's character with it.
* ``service.health_probe``: ``GET /healthz``.

Fetching an image found anywhere is guarded: ``http``/``https`` only, a public address only (never this
network's, the server's own, a link-local or a reserved one — checked at every redirect), an image only, at
most 8 MB; and through the outbound allow-list like every call Portalab makes.
"""

import ipaddress
import socket
from collections.abc import Sequence
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from portalab.capabilities.connector_sdk import CapabilityBinding, ServiceHandle, TestResult
from portalab.capabilities.health import HEALTH_PROBE
from portalab.capabilities.media import IMAGE_SEARCH, ImageHit
from portalab.capabilities.results import InvalidPayload
from portalab.connectors.http_base import HttpConnector, _Probe, binding
from portalab.core import egress

MAX_IMAGE = 8 * 1024 * 1024
REDIRECTS = 3
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Portalab", "Accept": "image/*"}


class UnsafeAddress(InvalidPayload):
    """An image address that is not on the public internet (or not an image)."""


def _size(value: Any) -> tuple[int, int]:
    """SearXNG's ``resolution``: ``1920x1080``, ``1920 x 1080`` or with a multiplication sign."""
    text = str(value or "").replace("\u00d7", "x").replace(" ", "")
    width, _, height = text.partition("x")
    return (int(width), int(height)) if width.isdigit() and height.isdigit() else (0, 0)


def map_hits(document: Any, limit: int) -> list[ImageHit]:
    out: list[ImageHit] = []
    for item in (document or {}).get("results") or []:
        url = item.get("img_src") if isinstance(item, dict) else None
        if not isinstance(url, str) or urlsplit(url).scheme not in ("http", "https"):
            continue
        width, height = _size(item.get("resolution"))
        out.append(
            ImageHit(
                url=url[:1000],
                title=str(item.get("title") or "")[:300],
                width=width,
                height=height,
                engine=str(item.get("engine") or "")[:40],
            )
        )
        if len(out) >= limit:
            break
    return out


def public(host: str) -> bool:
    """Every address the host resolves to is a public one."""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    addresses = {info[4][0] for info in infos}
    for address in addresses:
        ip = ipaddress.ip_address(str(address).split("%")[0])
        if not ip.is_global or ip.is_multicast:
            return False
    return bool(addresses)


class SearxngConnector(HttpConnector):
    key = "searxng"
    name = "SearXNG"
    description = (
        "A self-hosted metasearch engine: images found on the web, with no key (its JSON format on)."
    )
    icon = "search"
    category = "metadata"
    secret_fields: frozenset[str] = frozenset()
    provides: Sequence[CapabilityBinding] = (binding(IMAGE_SEARCH), binding(HEALTH_PROBE))
    status_path = "/healthz"

    def auth_headers(self, service: ServiceHandle) -> dict[str, str]:
        return {}

    async def version(self, service: ServiceHandle) -> str:
        found = await self.get_json(service, "/search", q="portalab", format="json")
        if not isinstance(found, dict) or "results" not in found:
            raise InvalidPayload("not SearXNG")
        return "SearXNG"

    async def test_connection(self, service: ServiceHandle) -> TestResult:
        try:
            await self.version(service)
        except (ConnectionError, OSError) as exc:
            if "403" in str(exc):
                return TestResult(
                    ok=False,
                    reachable=True,
                    authenticated=False,
                    compatible=False,
                    detail=(
                        "SearXNG answers but refuses JSON: add json to search: formats: in settings.yml."
                    ),
                )
            return TestResult(
                ok=False,
                reachable=False,
                authenticated=False,
                detail="Cannot reach the service: check the address, the port and that it is running.",
            )
        except InvalidPayload:
            return TestResult(
                ok=False,
                reachable=True,
                authenticated=False,
                compatible=False,
                detail="Something answered at this address, but it is not SearXNG.",
            )
        return TestResult(ok=True, reachable=True, authenticated=True, detail="Connected to SearXNG.")

    def provider(self, capability: str, service: ServiceHandle) -> Any:
        if capability == IMAGE_SEARCH:
            return _Images(self, service)
        if capability == HEALTH_PROBE:
            return _Probe(self, service)
        return None


class _Images:
    def __init__(self, connector: SearxngConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def images(self, query: str, limit: int = 30) -> list[ImageHit]:
        found = await self.connector.get_json(
            self.service, "/search", q=query[:200], categories="images", format="json"
        )
        return map_hits(found, limit)

    async def fetch(self, url: str) -> bytes:
        async with httpx.AsyncClient(
            timeout=10.0, follow_redirects=False, headers=HEADERS, event_hooks=egress.hooks()
        ) as client:
            for _ in range(REDIRECTS + 1):
                parts = urlsplit(url)
                if parts.scheme not in ("http", "https") or not parts.hostname or not public(parts.hostname):
                    raise UnsafeAddress("not a public image address")
                async with client.stream("GET", url) as response:
                    if response.is_redirect and response.headers.get("location"):
                        url = urljoin(url, response.headers["location"])
                        continue
                    if response.status_code >= 400:
                        raise ConnectionError(f"the image's host answered HTTP {response.status_code}")
                    if not response.headers.get("content-type", "").startswith("image/"):
                        raise UnsafeAddress("not an image")
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > MAX_IMAGE:
                            raise UnsafeAddress("image too large")
                    return bytes(data)
        raise UnsafeAddress("too many redirects")
