"""030 T054 (FR-024, issue 144) — the outbound allow-list: off, every call goes; on, only the hosts Portalab's
configuration declares and those the Admin lists (an asterisk for any subdomain); a refused call never leaves
and the declared hosts of a stopped plugin are forgotten."""

import httpx
import pytest

from portalab.core import egress
from portalab.core.egress import EgressPolicy, EgressRefused


@pytest.fixture(autouse=True)
def policy(monkeypatch: pytest.MonkeyPatch) -> EgressPolicy:
    fresh = EgressPolicy()
    monkeypatch.setattr(egress, "EGRESS", fresh)
    return fresh


async def _get(url: str) -> list[str]:
    sent: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        sent.append(str(request.url.host))
        return httpx.Response(200)

    async with httpx.AsyncClient(transport=httpx.MockTransport(answer), event_hooks=egress.hooks()) as client:
        await client.get(url)
    return sent


async def test_off_lets_everything_go(policy: EgressPolicy) -> None:
    assert await _get("https://anywhere.example.net/") == ["anywhere.example.net"]


async def test_on_only_known_hosts(policy: EgressPolicy) -> None:
    policy.configure(enabled=True, hosts=["status.example.org", "*.cdn.example.com"])
    policy.allow("plex.lan", "service")
    policy.allow("api.example.org", "plugin:weather")
    for url in (
        "https://status.example.org/",
        "https://a.cdn.example.com/x",
        "http://plex.lan:32400/",
        "https://api.example.org/",
    ):
        assert len(await _get(url)) == 1, url
    for url in (
        "https://evil.example.net/",
        "https://cdn.example.com.evil.net/",
        "http://169.254.169.254/latest",
    ):
        with pytest.raises(EgressRefused):
            await _get(url)
    policy.forget("plugin:weather")
    with pytest.raises(EgressRefused):
        await _get("https://api.example.org/")
    assert "plex.lan" in policy.snapshot()["declared"]
