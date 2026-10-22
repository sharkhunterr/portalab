"""Conditions (T016; R5, R6): a closed catalog evaluated with AND semantics inside a modifier — ``activity``
(event type), ``media_kind``, ``genre`` (canonical normalized tags), ``title_contains`` (NFKC, casefold,
diacritics-insensitive, on original and effective titles) and ``audience`` (all | roles | users | level
range). Attributes come from ``activity.attributes`` providers; when an attribute a condition needs is
unknown, the result is *unknown* and the modifier is **not applied** (no false grant)."""

import asyncio
from collections.abc import Mapping
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.activity import CAPABILITY as ACTIVITY
from portalab.capabilities.activity import ActivityAttributes
from portalab.capabilities.i18n import normalize_for_search
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.statistics import PROGRESSION
from portalab.capabilities.user_grants import ROLES_CAPABILITY
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.campaigns.definitions.schema import Audience, When
from portalab.modules.campaigns.models import AttributeFailure
from portalab.modules.campaigns.observability import log, metrics

Verdict = Literal["match", "no_match", "unknown"]
TIMEOUT = 2.0


def norm(value: str) -> str:
    return normalize_for_search(value, None)


def needs_attributes(when: When) -> bool:
    return bool(when.media_kind or when.genre or when.title_contains or when.keyword or when.objects)


def _themed(when: When, attributes: ActivityAttributes) -> Verdict:
    """« title contains », « keyword » and « hand-picked »: any one of them is enough (a Christmas film is
    one whose title says so, or whose keywords do, or that was picked)."""
    asked = [bool(when.title_contains), bool(when.keyword), bool(when.objects)]
    if not any(asked):
        return "match"
    known = False
    if when.objects:
        known = True
        if set(attributes.objects) & {o.strip() for o in when.objects}:
            return "match"
    if when.keyword and attributes.keywords:
        known = True
        keywords = [norm(k) for k in attributes.keywords]
        if any(norm(fragment) in keyword for fragment in when.keyword for keyword in keywords):
            return "match"
    if when.title_contains:
        titles = [norm(t) for t in (attributes.title, attributes.original_title) if t]
        if titles:
            known = True
            if any(norm(fragment) in title for fragment in when.title_contains for title in titles):
                return "match"
    return "no_match" if known else "unknown"


def match_attributes(when: When, attributes: ActivityAttributes | None) -> Verdict:
    if not needs_attributes(when):
        return "match"
    if attributes is None:
        return "unknown"
    if when.media_kind:
        if attributes.media_kind is None:
            return "unknown"
        if norm(attributes.media_kind) not in {norm(k) for k in when.media_kind}:
            return "no_match"
    if when.genre:
        if not attributes.genres:
            return "unknown"
        if not {norm(g) for g in attributes.genres} & {norm(g) for g in when.genre}:
            return "no_match"
    return _themed(when, attributes)


class Matcher:
    def __init__(
        self,
        capabilities: CapabilityRegistry,
        database: Database,
        *,
        record_failures: bool = True,
        clock: Clock | None = None,
    ) -> None:
        self.capabilities = capabilities
        self.database = database
        self.record_failures = record_failures
        self.clock = clock

    def _providers(self, name: str) -> list[Any]:
        try:
            return [p.provider for p in self.capabilities.system_providers(name)]
        except Exception:
            return []

    async def attributes(self, event_type: str, payload: Mapping[str, Any]) -> ActivityAttributes | None:
        for provider in self._providers(ACTIVITY):
            try:
                if not provider.handles(event_type):
                    continue
                found = await asyncio.wait_for(provider.attributes(event_type, dict(payload)), TIMEOUT)
            except Exception:
                found = None
            if isinstance(found, ActivityAttributes):
                return found
            await self.failed(event_type)
            return None
        return None

    async def failed(self, event_type: str) -> None:
        metrics.increment("campaigns.attributes.unavailable")
        if not self.record_failures:
            return
        try:
            async with self.database.unit_of_work() as uow:
                statement = insert(AttributeFailure).values(
                    day=utc_now(self.clock).date(), event_type=event_type[:128], count=1
                )
                await uow.session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[AttributeFailure.day, AttributeFailure.event_type],
                        set_={"count": AttributeFailure.count + 1},
                    )
                )
        except Exception:
            log.warning("attribute failure not recorded")

    async def in_audience(self, audience: Audience, user: UUID) -> bool:
        if audience.kind == "all":
            return True
        if audience.kind == "users":
            return str(user) in set(audience.users)
        if audience.kind == "roles":
            providers = self._providers(ROLES_CAPABILITY)
            if not providers:
                return False
            try:
                roles = await asyncio.wait_for(providers[0].roles_of(user), TIMEOUT)
            except Exception:
                return False
            return bool(set(roles) & set(audience.roles))
        providers = self._providers(PROGRESSION)
        if not providers:
            return False
        try:
            level = int(await asyncio.wait_for(providers[0].level(user), TIMEOUT))
        except Exception:
            return False
        low, high = audience.min_level or 1, audience.max_level or 10_000
        return low <= level <= high
