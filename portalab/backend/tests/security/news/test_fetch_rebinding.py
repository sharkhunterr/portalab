"""Issue 401 — fetching a news source connects to the very address that was checked public: a DNS answer
that changes between the check and the connection (rebinding to the local network) changes nothing; the
site's name stays in the Host header and the TLS handshake, and the outbound allow-list still reads it."""

import httpx
import pytest

from portalab.core.egress import EGRESS
from portalab.modules.news.sources.fetch import fetch

pytestmark = pytest.mark.unit
RSS = b"<rss version='2.0'><channel><title>x</title></channel></rss>"


def rebinding() -> object:
    answers = iter([["93.184.216.34"], ["127.0.0.1"]])  # public when checked, local the second time

    async def resolve(_host: str) -> list[str]:
        return next(answers)

    return resolve


async def test_the_connection_goes_to_the_checked_address() -> None:
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=RSS, headers={"content-type": "application/rss+xml"})

    fetched = await fetch(
        "https://news.example.org/feed.xml", resolver=rebinding(), transport=httpx.MockTransport(answer)
    )  # type: ignore[arg-type]
    assert fetched.status == 200 and fetched.url == "https://news.example.org/feed.xml"
    [request] = seen
    assert request.url.host == "93.184.216.34"  # the checked address, never a second lookup
    assert request.headers["host"] == "news.example.org"
    assert request.extensions["sni_hostname"] == "news.example.org"
    assert request.extensions["egress_host"] == "news.example.org"


async def test_the_allow_list_reads_the_name_not_the_address() -> None:
    """A connection to an address carries the name it is for; a header naming a host proves nothing."""
    from portalab.core.egress import EgressRefused, _check

    EGRESS.configure(enabled=True, hosts=["news.example.org"])
    try:
        pinned = httpx.Request(
            "GET", "https://93.184.216.34/feed", extensions={"egress_host": "news.example.org"}
        )
        await _check(pinned)
        forged = httpx.Request("GET", "https://10.0.0.5/feed", headers={"Host": "news.example.org"})
        with pytest.raises(EgressRefused):
            await _check(forged)
    finally:
        EGRESS.configure(enabled=False, hosts=[])
