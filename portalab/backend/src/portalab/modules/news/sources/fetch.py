"""#299: reading an address an editor gave, safely — http(s) only, a public address unless the portal allows
its own network (a source on the LAN), every redirect checked again, a size and a time limit, the outbound
allow-list honoured. Never a member's cookie or token: nothing but the URL is sent."""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from portalab.core.egress import EGRESS, hooks

TIMEOUT = 10.0
REDIRECTS = 3
MAX_FEED = 3 * 1024 * 1024
MAX_IMAGE = 4 * 1024 * 1024
AGENT = "Portalab news reader (+https://github.com/portalab)"
Resolver = Callable[[str], Awaitable[list[str]]]


class FetchFailed(Exception):
    """Why a source could not be read, in a few words an editor understands."""


@dataclass(frozen=True, slots=True)
class Fetched:
    url: str  # where it was found in the end (after the redirects)
    status: int  # 200, or 304 (not changed since)
    content_type: str
    body: bytes
    etag: str | None = None
    modified: str | None = None


def is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%")[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return bool(ip.is_global) and not (ip.is_multicast or ip.is_reserved)


async def resolve(host: str) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return list({str(info[4][0]) for info in infos})


async def fetch(
    url: str,
    *,
    allow_private: bool = False,
    max_bytes: int = MAX_FEED,
    accept: str = "application/rss+xml, application/atom+xml, application/xml, text/xml, text/html;q=0.8",
    etag: str | None = None,
    modified: str | None = None,
    resolver: Resolver = resolve,
    transport: httpx.AsyncBaseTransport | None = None,
) -> Fetched:
    headers = {"User-Agent": AGENT, "Accept": accept}
    try:
        host = (httpx.URL(url).host or "").lower()
    except (httpx.InvalidURL, ValueError, UnicodeError) as exc:  # issue 401: what a request sent
        raise FetchFailed("not a valid address") from exc
    if host == "youtube.com" or host.endswith(".youtube.com"):
        # YouTube shows Europe its consent page first: the « refused » answer, a cookie of YouTube's own
        headers["Cookie"] = "SOCS=CAI"
    if etag:
        headers["If-None-Match"] = etag
    if modified:
        headers["If-Modified-Since"] = modified
    async with httpx.AsyncClient(
        timeout=TIMEOUT, follow_redirects=False, event_hooks=hooks(), transport=transport
    ) as client:
        for _ in range(REDIRECTS + 1):
            target = httpx.URL(url)
            if target.scheme not in ("http", "https") or not target.host:
                raise FetchFailed("only http and https addresses")
            connect, sent = target, dict(headers)
            extensions: dict[str, str] = {}
            if not allow_private:
                try:
                    addresses = await resolver(target.host)
                except (OSError, UnicodeError) as exc:  # issue 401: a name too long for the DNS too
                    raise FetchFailed("this address does not resolve") from exc
                if not addresses or not all(is_public(a) for a in addresses):
                    raise FetchFailed("a private address (allow the local network in the settings)")
                # issue 401: the connection goes to the address just checked, never to a second lookup (a DNS
                # answer changed in between — rebinding — would reach the local network); the site's name
                # stays in the Host header and the TLS handshake
                connect = target.copy_with(host=addresses[0])
                sent["Host"] = target.netloc.decode("ascii")
                extensions = {"egress_host": target.host}
                if target.scheme == "https":
                    extensions["sni_hostname"] = target.host
            EGRESS.allow(target.host, "news.sources")
            try:
                async with client.stream("GET", connect, headers=sent, extensions=extensions) as response:
                    if response.status_code in (301, 302, 303, 307, 308) and "location" in response.headers:
                        url = urljoin(url, response.headers["location"])
                        continue
                    if response.status_code == 304:
                        return Fetched(url, 304, "", b"", etag, modified)
                    if response.status_code >= 400:
                        raise FetchFailed(f"the site answered {response.status_code}")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body += chunk
                        if len(body) > max_bytes:
                            raise FetchFailed("too large")
                    return Fetched(
                        url,
                        response.status_code,
                        response.headers.get("content-type", "").split(";")[0].strip().lower(),
                        bytes(body),
                        response.headers.get("etag"),
                        response.headers.get("last-modified"),
                    )
            except httpx.TimeoutException as exc:
                raise FetchFailed("the site took too long") from exc
            except httpx.HTTPError as exc:
                raise FetchFailed("the site could not be reached") from exc
    raise FetchFailed("too many redirects")
