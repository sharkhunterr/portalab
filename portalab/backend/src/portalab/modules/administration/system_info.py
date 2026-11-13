"""Issue 410 — what the Version page tells beyond the version: the image's build, whether a newer Portalab is
released on GitHub, and the portal's security posture, each point with what to do.

The update check reads GitHub's public releases API for this project only — nothing about the portal is sent
(no identifier, no version in the request) — at most twice a day, never when the Admin turned it off, and
through the outbound allow-list. Only a version number is taken from the answer; the link shown is built
here, never taken from it.
"""

import asyncio
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from portalab.core import egress
from portalab.core.logging import get_logger

log = get_logger("portalab.administration")

REPOSITORY = "sharkhunterr/portalab"
LATEST = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
RELEASES = f"https://github.com/{REPOSITORY}/releases"
TAG = re.compile(r"v?(\d{1,4})\.(\d{1,4})\.(\d{1,4})")
FRESH = timedelta(hours=12)
RETRY = timedelta(minutes=15)  # after a failure, GitHub is asked again a little later — never in a loop
MAX_BYTES = 512 * 1024
TIMEOUT = httpx.Timeout(8.0, connect=5.0)
SETTING = "admin.updateCheck"

egress.EGRESS.allow("api.github.com", "update check")


def parse_version(text: str | None) -> tuple[int, int, int] | None:
    match = TAG.fullmatch(text or "")
    return (int(match[1]), int(match[2]), int(match[3])) if match else None


@dataclass(slots=True)
class UpdateStatus:
    latest: str | None = None
    published_at: str | None = None
    checked_at: datetime | None = None
    error: str | None = None

    def as_dict(self, current: str) -> dict[str, Any]:
        mine, theirs = parse_version(current), parse_version(self.latest)
        return {
            "enabled": True,
            "current": current,
            "latest": self.latest,
            "update_available": bool(mine and theirs and theirs > mine),
            "url": f"{RELEASES}/tag/v{self.latest}" if self.latest else RELEASES,
            "published_at": self.published_at,
            "checked_at": self.checked_at.isoformat(timespec="seconds") if self.checked_at else None,
            "error": self.error,
        }


@dataclass
class UpdateCheck:
    """The latest release, kept for a while: GitHub is asked when the page wants it and it is stale."""

    client: httpx.AsyncClient | None = None
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    status: UpdateStatus = field(default_factory=UpdateStatus)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def _stale(self) -> bool:
        checked = self.status.checked_at
        if checked is None:
            return True
        return self.now() - checked > (RETRY if self.status.error else FRESH)

    async def get(self, *, force: bool = False) -> UpdateStatus:
        async with self._lock:
            if force or self._stale():
                try:
                    self.status = UpdateStatus(*await self._fetch(), checked_at=self.now())
                except (httpx.HTTPError, ValueError) as error:
                    log.info("update check failed", extra={"fields": {"error": type(error).__name__}})
                    self.status = UpdateStatus(
                        self.status.latest, self.status.published_at, self.now(), _reason(error)
                    )
            return self.status

    async def _fetch(self) -> tuple[str | None, str | None]:
        if self.client is not None:
            return await self._read(self.client)
        async with httpx.AsyncClient(timeout=TIMEOUT, event_hooks=egress.hooks()) as client:
            return await self._read(client)

    async def _read(self, client: httpx.AsyncClient) -> tuple[str | None, str | None]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "portalab-update-check",
        }
        async with client.stream("GET", LATEST, headers=headers, follow_redirects=False) as response:
            if response.status_code == 404:  # no release published yet
                return None, None
            if response.status_code != 200:
                raise ValueError(f"github:{response.status_code}")
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    raise ValueError("github:too_large")
        data = httpx.Response(200, content=bytes(body)).json()
        if not isinstance(data, dict):
            raise ValueError("github:unexpected")
        version = parse_version(str(data.get("tag_name") or ""))
        if version is None:
            raise ValueError("github:unexpected")
        published = data.get("published_at")
        published = published if isinstance(published, str) and len(published) <= 40 else None
        return ".".join(map(str, version)), published


def _reason(error: Exception) -> str:
    if isinstance(error, egress.EgressRefused):
        return "egress"
    if isinstance(error, httpx.TimeoutException):
        return "timeout"
    if isinstance(error, httpx.HTTPError):
        return "network"
    text = str(error)
    return text if text.startswith("github:") else "github:unexpected"


def build() -> dict[str, str | None]:
    """The image's build (set by the Dockerfile from the CI): none when run from the source."""
    ref = os.environ.get("PORTALAB_BUILD_REF", "").strip()
    date = os.environ.get("PORTALAB_BUILD_DATE", "").strip()
    return {
        "commit": ref[:40] if re.fullmatch(r"[0-9a-f]{7,40}", ref) else None,
        "date": date[:40] if date and date != "unknown" else None,
    }


# --- the security posture ----------------------------------------------------------------------------------
async def posture(
    read: Callable[[str], Any],
    *,
    https: bool,
    own_mfa: bool | None,
    mfa_members: int | None,
    last_backup: datetime | None,
    now: datetime,
) -> list[dict[str, Any]]:
    """Each point: its key, ``ok`` / ``warn`` / ``info``, a few values for its sentence, and the setting that
    changes it (the interface links to it)."""

    async def value(key: str, fallback: Any = None) -> Any:
        try:
            return await read(key)
        except Exception:  # an unknown or unreadable setting is left out of the picture, never an error
            return fallback

    points: list[dict[str, Any]] = [
        {"key": "transport", "level": "ok" if https else "warn", "values": {}, "setting": None}
    ]
    if own_mfa is not None:
        points.append(
            {
                "key": "mfa",
                "level": "ok" if own_mfa else "warn",
                "values": {"own": own_mfa, "members": mfa_members or 0},
                "setting": None,
            }
        )
    policy = await value("identity.passwordPolicy")
    raw = policy.get("min_length") if isinstance(policy, dict) else getattr(policy, "min_length", None)
    length = raw if isinstance(raw, int) else 0
    if length:
        points.append(
            {
                "key": "password",
                "level": "ok" if length >= 12 else "warn",
                "values": {"min": length},
                "setting": "identity.passwordPolicy",
            }
        )
    if await value("identity.oidc.enabled", False):
        trusts = bool(await value("identity.oidc.trustUnverifiedEmail", False))
        points.append(
            {
                "key": "sso",
                "level": "warn" if trusts else "ok",
                "values": {},
                "setting": "identity.oidc.trustUnverifiedEmail",
            }
        )
    egress_on = bool(await value("security.egress.enabled", False))
    points.append(
        {
            "key": "egress",
            "level": "ok" if egress_on else "info",
            "values": {},
            "setting": "security.egress.enabled",
        }
    )
    if await value("observability.metricsEndpointEnabled", False):
        token = await value("observability.metricsToken", None)
        points.append(
            {
                "key": "metrics",
                "level": "ok" if token else "warn",
                "values": {},
                "setting": "observability.metricsToken",
            }
        )
    if await value("notifications.email.enabled", False):
        tls = bool(await value("notifications.email.smtp.tls", False))
        points.append(
            {
                "key": "smtp",
                "level": "ok" if tls else "warn",
                "values": {},
                "setting": "notifications.email.smtp.tls",
            }
        )
    days = (now - last_backup).days if last_backup else None
    points.append(
        {
            "key": "backup",
            "level": "ok" if days is not None and days <= 7 else "warn",
            "values": {"days": days},
            "setting": None,
        }
    )
    return points


UPDATES = UpdateCheck()
