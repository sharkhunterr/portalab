"""Issue 410 — the update check reads only a version number from GitHub's releases API (the link is built
here), keeps it twelve hours, tries again a little later after a failure, refuses odd or oversized answers
and goes through the outbound allow-list; the security posture says what to do for each point."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from portalab.core import egress
from portalab.modules.administration.system_info import (
    LATEST,
    MAX_BYTES,
    UpdateCheck,
    build,
    parse_version,
    posture,
)

NOW = datetime(2026, 11, 13, 18, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.at = NOW

    def __call__(self) -> datetime:
        return self.at


def github(answers: list[httpx.Response]) -> tuple[httpx.AsyncClient, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return answers.pop(0)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler), event_hooks=egress.hooks()), seen


def release(tag: str, **extra: Any) -> httpx.Response:
    body = {"tag_name": tag, "published_at": "2026-11-13T17:50:00Z", "html_url": "https://evil.example/x"}
    return httpx.Response(200, json={**body, **extra})


def test_versions() -> None:
    assert parse_version("v1.4.0") == (1, 4, 0)
    assert parse_version("1.10.2") == (1, 10, 2)
    for odd in ("", None, "v1.4", "1.4.0-rc1", "latest", "v1.4.0\n", "v99999.0.0"):
        assert parse_version(odd) is None


async def test_newer_release_found_and_kept() -> None:
    client, seen = github([release("v1.5.0")])
    check = UpdateCheck(client=client, now=Clock())
    status = (await check.get()).as_dict("1.4.0")
    assert status["latest"] == "1.5.0" and status["update_available"] is True
    assert (
        status["url"] == "https://github.com/sharkhunterr/portalab/releases/tag/v1.5.0"
    )  # never the answer's
    assert str(seen[0].url) == LATEST
    assert "portalab" not in seen[0].headers.get("user-agent", "").replace("portalab-update-check", "")
    assert not seen[0].url.query  # nothing about this portal is sent
    await check.get()
    assert len(seen) == 1  # kept: GitHub is not asked again before twelve hours


async def test_up_to_date_and_older() -> None:
    client, _ = github([release("v1.4.0")])
    assert (await UpdateCheck(client=client).get()).as_dict("1.4.0")["update_available"] is False
    client, _ = github([release("1.3.9")])
    assert (await UpdateCheck(client=client).get()).as_dict("1.4.0")["update_available"] is False


async def test_stale_after_twelve_hours_and_forced() -> None:
    clock = Clock()
    client, seen = github([release("v1.4.0"), release("v1.4.1"), release("v1.4.2")])
    check = UpdateCheck(client=client, now=clock)
    await check.get()
    clock.at += timedelta(hours=13)
    assert (await check.get()).latest == "1.4.1"
    assert (await check.get(force=True)).latest == "1.4.2"
    assert len(seen) == 3


@pytest.mark.parametrize(
    ("answer", "reason"),
    [
        (httpx.Response(500), "github:500"),
        (httpx.Response(302, headers={"location": "https://evil.example/"}), "github:302"),
        (release("not-a-version"), "github:unexpected"),
        (httpx.Response(200, json=["a", "list"]), "github:unexpected"),
        (httpx.Response(200, content=b"{" + b" " * (MAX_BYTES + 10) + b"}"), "github:too_large"),
    ],
)
async def test_odd_answers_are_refused(answer: httpx.Response, reason: str) -> None:
    clock = Clock()
    client, seen = github([release("v1.4.0"), answer, release("v1.4.1")])
    check = UpdateCheck(client=client, now=clock)
    await check.get()
    status = await check.get(force=True)
    assert status.error == reason and status.latest == "1.4.0"  # the last known release is kept
    await check.get()
    assert len(seen) == 2  # not asked again at once after a failure
    clock.at += timedelta(minutes=16)
    assert (await check.get()).latest == "1.4.1"


async def test_no_release_yet() -> None:
    client, _ = github([httpx.Response(404)])
    status = (await UpdateCheck(client=client).get()).as_dict("1.4.0")
    assert status["latest"] is None and status["update_available"] is False and status["error"] is None


async def test_the_outbound_allow_list_applies() -> None:
    client, seen = github([release("v9.9.9")])
    before = (egress.EGRESS.enabled, set(egress.EGRESS.listed), dict(egress.EGRESS.declared))
    try:
        egress.EGRESS.configure(enabled=True)
        egress.EGRESS.forget("update check")
        egress.EGRESS.forget("pack sources")
        status = await UpdateCheck(client=client).get()
    finally:
        egress.EGRESS.enabled, egress.EGRESS.listed = before[0], before[1]
        egress.EGRESS.declared.clear()
        egress.EGRESS.declared.update(before[2])
    assert status.error == "egress" and status.latest is None and seen == []


async def test_a_timeout_is_a_failure_not_an_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    status = await UpdateCheck(client=client).get()
    assert status.error == "timeout"


def test_build(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORTALAB_BUILD_REF", "4d0c91c7268097ee41665e209742689a68cef054")
    monkeypatch.setenv("PORTALAB_BUILD_DATE", "2026-11-13T17:40:00Z")
    assert build() == {"commit": "4d0c91c7268097ee41665e209742689a68cef054", "date": "2026-11-13T17:40:00Z"}
    monkeypatch.setenv("PORTALAB_BUILD_REF", "<script>")
    monkeypatch.setenv("PORTALAB_BUILD_DATE", "unknown")
    assert build() == {"commit": None, "date": None}


async def test_posture() -> None:
    settings: dict[str, Any] = {
        "identity.passwordPolicy": {"min_length": 10},
        "identity.oidc.enabled": True,
        "identity.oidc.trustUnverifiedEmail": True,
        "security.egress.enabled": False,
        "observability.metricsEndpointEnabled": True,
        "observability.metricsToken": None,
        "notifications.email.enabled": True,
        "notifications.email.smtp.tls": False,
    }

    async def read(key: str) -> Any:
        return settings[key]

    points = await posture(read, https=False, own_mfa=False, mfa_members=3, last_backup=None, now=NOW)
    levels = {p["key"]: p["level"] for p in points}
    assert levels == {
        "transport": "warn",
        "mfa": "warn",
        "password": "warn",
        "sso": "warn",
        "egress": "info",
        "metrics": "warn",
        "smtp": "warn",
        "backup": "warn",
    }
    assert next(p for p in points if p["key"] == "mfa")["values"] == {"own": False, "members": 3}
    json.dumps(points)  # what the API answers

    settings.update(
        {
            "identity.passwordPolicy": {"min_length": 14},
            "identity.oidc.trustUnverifiedEmail": False,
            "security.egress.enabled": True,
            "observability.metricsToken": "set",
            "notifications.email.smtp.tls": True,
        }
    )
    good = await posture(
        read, https=True, own_mfa=True, mfa_members=1, last_backup=NOW - timedelta(days=2), now=NOW
    )
    assert {p["level"] for p in good} == {"ok"}


async def test_posture_leaves_out_what_is_off_or_unknown() -> None:
    async def read(key: str) -> Any:
        if key == "identity.passwordPolicy":
            raise KeyError(key)
        return False

    points = await posture(read, https=True, own_mfa=None, mfa_members=None, last_backup=None, now=NOW)
    assert [p["key"] for p in points] == ["transport", "egress", "backup"]
