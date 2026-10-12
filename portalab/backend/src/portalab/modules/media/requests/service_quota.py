"""#3: the request service's own quotas (Seerr), steered from the portal.

One truth: when a member's account on the request service is linked, *its* limits decide (films and
series apart, a number of requests per number of days) — the portal reads them before a request and shows
them; its own allowance per period applies only to members without a linked account. A unit bought in the
shop lets one more request through once the service's limit is reached (sent so it does not count there).
Administrators read and set every account's limits and the service's defaults from the portal (audited
by the API layer).
"""

import asyncio
import time
from contextlib import suppress
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.capabilities.media import (
    REQUEST_QUOTAS,
    REQUESTS,
    QuotaAccount,
    QuotaLimits,
    QuotaWindow,
    SourceQuota,
    unwrap,
)
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.errors import Unavailable
from portalab.core.time import Clock, utc_now
from portalab.modules.media.models import MediaRequest, UserLink
from portalab.modules.media.observability import log

TTL = 20.0
TIMEOUT = 10.0
SERIES = ("series", "season", "episode")


class QuotasUnavailable(Unavailable):
    default_code = "media.quotas_unavailable"
    default_title = "The request service's quotas are not available"


def kind_of(kind: str) -> str:
    """The quota a request counts against: ``movie`` or ``tv``."""
    return "tv" if kind in SERIES else "movie"


def window_out(window: QuotaWindow, renews_at: datetime | None = None) -> dict[str, Any]:
    return {
        "limit": window.limit,
        "days": window.days,
        "used": window.used,
        "remaining": window.remaining,
        "restricted": window.restricted,
        "renews_at": renews_at.isoformat() if renews_at else None,
    }


def limits_out(limits: QuotaLimits) -> dict[str, Any]:
    return {
        "movie": {"limit": limits.movie_limit, "days": limits.movie_days},
        "tv": {"limit": limits.tv_limit, "days": limits.tv_days},
    }


class ServiceQuotas:
    def __init__(self, database: Database, capabilities: CapabilityRegistry, *, clock: Clock | None = None):
        self.database = database
        self.capabilities = capabilities
        self.clock = clock
        self._cache: dict[tuple[UUID, UUID], tuple[float, SourceQuota]] = {}

    # --- providers ------------------------------------------------------------------------------------
    def _quota_providers(self) -> dict[UUID, Any]:
        out: dict[UUID, Any] = {}
        with suppress(Exception):
            for registration in self.capabilities.system_providers(REQUEST_QUOTAS):
                with suppress(ValueError):
                    out[UUID(registration.instance_ref)] = registration.provider
        return out

    def _request_services(self) -> list[UUID]:
        out: list[UUID] = []
        with suppress(Exception):
            for registration in self.capabilities.system_providers(REQUESTS):
                with suppress(ValueError):
                    out.append(UUID(registration.instance_ref))
        return out

    def managed(self) -> tuple[UUID, Any] | None:
        """The request service whose quotas the portal steers (the first one that has quotas)."""
        quotas = self._quota_providers()
        for service in self._request_services():
            if service in quotas:
                return service, quotas[service]
        return next(iter(quotas.items()), None)

    async def _account(self, user: UUID, service: UUID) -> str | None:
        async with self.database.session() as session:
            return (
                await session.execute(
                    select(UserLink.external_user_id).where(
                        UserLink.user_id == user,
                        UserLink.service_id == service,
                        UserLink.verified.is_(True),
                    )
                )
            ).scalar_one_or_none()

    # --- a member's quota -----------------------------------------------------------------------------
    async def check(self, user: UUID, service: UUID) -> SourceQuota | None:
        """The member's quota on this request service now — ``None`` when it has no quotas or the member's
        account is not linked (the portal's own allowance applies)."""
        provider = self._quota_providers().get(service)
        if provider is None:
            return None
        account = await self._account(user, service)
        if account is None:
            return None
        cached = self._cache.get((user, service))
        if cached and time.monotonic() - cached[0] < TTL:
            return cached[1]
        try:
            quota = unwrap(await asyncio.wait_for(provider.quota(account), timeout=TIMEOUT))
        except Exception as exc:
            log.info("request quota unavailable", extra={"reason": type(exc).__name__})
            raise QuotasUnavailable("The request service did not say how many requests are left.") from exc
        self._cache[(user, service)] = (time.monotonic(), quota)
        return quota  # type: ignore[no-any-return]

    def forget(self, user: UUID | None = None) -> None:
        if user is None:
            self._cache.clear()
        else:
            for key in [k for k in self._cache if k[0] == user]:
                del self._cache[key]

    async def _renewals(self, user: UUID, quota: SourceQuota) -> dict[str, datetime | None]:
        """When a request comes back: the day the oldest one still counting leaves the window."""
        now = utc_now(self.clock)
        out: dict[str, datetime | None] = {"movie": None, "tv": None}
        async with self.database.session() as session:
            rows = list(
                (
                    await session.execute(
                        select(MediaRequest.requested_at, MediaRequest.external_ref).where(
                            MediaRequest.requester_user_id == user,
                            MediaRequest.state.not_in(("declined", "cancelled", "failed")),
                            MediaRequest.counted != "extra",
                            MediaRequest.requested_at >= now - timedelta(days=366),
                        )
                    )
                ).all()
            )
        for kind, window in (("movie", quota.movie), ("tv", quota.tv)):
            if not window.limit or not window.days or not window.restricted:
                continue
            since = now - timedelta(days=window.days)
            times = sorted(
                at for at, ref in rows if at >= since and kind_of(str((ref or {}).get("kind") or "")) == kind
            )
            if times:
                out[kind] = times[max(0, len(times) - window.limit)] + timedelta(days=window.days)
        return out

    async def summary(self, user: UUID) -> dict[str, Any] | None:
        managed = self.managed()
        if managed is None:
            return None
        try:
            quota = await self.check(user, managed[0])
        except QuotasUnavailable:
            return {"linked": True, "available": False}
        if quota is None:
            return {"linked": False}
        renewals = await self._renewals(user, quota)
        return {
            "linked": True,
            "available": True,
            "movie": window_out(quota.movie, renewals["movie"]),
            "tv": window_out(quota.tv, renewals["tv"]),
        }

    # --- administration -------------------------------------------------------------------------------
    def _require(self) -> tuple[UUID, Any]:
        managed = self.managed()
        if managed is None:
            raise QuotasUnavailable("No request service with quotas is connected.")
        return managed

    async def overview(self) -> dict[str, Any]:
        """Every account of the request service with its limits, what it used, and the member it is."""
        service, provider = self._require()
        try:
            accounts: list[QuotaAccount] = list(
                unwrap(await asyncio.wait_for(provider.accounts(), timeout=60))
            )
            defaults: QuotaLimits = unwrap(await asyncio.wait_for(provider.defaults(), timeout=TIMEOUT))
        except Exception as exc:
            raise QuotasUnavailable("The request service did not answer.") from exc
        async with self.database.session() as session:
            links = {
                external: user
                for external, user in await session.execute(
                    select(UserLink.external_user_id, UserLink.user_id).where(
                        UserLink.service_id == service, UserLink.verified.is_(True)
                    )
                )
            }
        names = await self._member_names(set(links.values()))
        rows = []
        for account in accounts:
            member = links.get(account.external_id)
            rows.append(
                {
                    "account": account.external_id,
                    "name": account.name,
                    "member": {"id": str(member), "name": names.get(member)} if member else None,
                    "exempt": account.exempt,
                    "own": limits_out(account.own),
                    "movie": window_out(account.quota.movie) if account.quota else None,
                    "tv": window_out(account.quota.tv) if account.quota else None,
                }
            )
        rows.sort(key=lambda r: (r["member"] is None, r["exempt"], str(r["name"] or "").casefold()))
        return {"service_id": str(service), "defaults": limits_out(defaults), "accounts": rows}

    async def _member_names(self, users: set[UUID]) -> dict[UUID, str | None]:
        out: dict[UUID, str | None] = {}
        with suppress(Exception):
            directory = self.capabilities.system_providers(DIRECTORY)[0].provider
            for user in users:
                with suppress(Exception):
                    found = await directory.get_user_summary(user)
                    out[user] = found.display_name if found else None
        return out

    async def set_limits(self, account: str, limits: QuotaLimits) -> None:
        _, provider = self._require()
        try:
            await asyncio.wait_for(provider.set_limits(account, limits), timeout=TIMEOUT)
        except Exception as exc:
            raise QuotasUnavailable("The request service did not take the new limits.") from exc
        self.forget()

    async def set_defaults(self, limits: QuotaLimits) -> None:
        _, provider = self._require()
        try:
            await asyncio.wait_for(provider.set_defaults(limits), timeout=TIMEOUT)
        except Exception as exc:
            raise QuotasUnavailable("The request service did not take the new defaults.") from exc
        self.forget()
