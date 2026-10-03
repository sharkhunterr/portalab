"""Built-in condition leaves (T018; R3) over existing ports: ``user_is``, ``role_in``, ``level_at_least``
(013), ``service_state_in`` (006), ``media_kind`` / ``genre`` / ``title_contains`` (``activity.attributes``,
026 normalization), ``campaign_active`` (014), ``time_window`` (026 zones), ``permission_held`` (003 —
informational, it never grants anything) and ``event_field`` (declared attributes)."""

import asyncio
from collections.abc import Mapping
from datetime import time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from portalab.capabilities.activity import CAPABILITY as ACTIVITY
from portalab.capabilities.automations import ConditionLeaf, ConditionRegistry, LeafContext
from portalab.capabilities.campaigns import READER as CAMPAIGNS
from portalab.capabilities.health import SERVICE_STATE
from portalab.capabilities.i18n import normalize_for_search
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.statistics import PROGRESSION
from portalab.capabilities.user_grants import ROLES_CAPABILITY
from portalab.core.authz_port import Authorizer, Principal

OWNER = "module:automations"


def _provider(capabilities: CapabilityRegistry, name: str) -> Any | None:
    try:
        providers = capabilities.system_providers(name)
    except Exception:
        return None
    return providers[0].provider if providers else None


def compare(actual: Any, op: str, expected: Any) -> bool | None:
    if actual is None:
        return None
    try:
        match op:
            case "eq":
                return bool(actual == expected)
            case "ne":
                return bool(actual != expected)
            case "in":
                return actual in (expected if isinstance(expected, list) else [expected])
            case "contains":
                return normalize_for_search(str(expected), None) in normalize_for_search(str(actual), None)
            case "gt":
                return bool(actual > expected)
            case "gte":
                return bool(actual >= expected)
            case "lt":
                return bool(actual < expected)
            case "lte":
                return bool(actual <= expected)
    except TypeError:
        return None
    return None


def register_builtin(
    registry: ConditionRegistry, capabilities: CapabilityRegistry, authorizer: Authorizer
) -> None:
    async def user_is(ctx: LeafContext, p: Mapping[str, Any]) -> bool | None:
        return (
            None
            if ctx.subject_user is None
            else str(ctx.subject_user) in {str(u) for u in p.get("users", [])}
        )

    async def role_in(ctx: LeafContext, p: Mapping[str, Any]) -> bool | None:
        roles = _provider(capabilities, ROLES_CAPABILITY)
        if roles is None or ctx.subject_user is None:
            return None
        return bool(set(await roles.roles_of(ctx.subject_user)) & set(p.get("roles", [])))

    async def level_at_least(ctx: LeafContext, p: Mapping[str, Any]) -> bool | None:
        progression = _provider(capabilities, PROGRESSION)
        if progression is None or ctx.subject_user is None:
            return None
        return int(await progression.level(ctx.subject_user)) >= int(p.get("level", 1))

    async def service_state_in(ctx: LeafContext, p: Mapping[str, Any]) -> bool | None:
        states = _provider(capabilities, SERVICE_STATE)
        if states is None:
            return None
        view = await states.get(str(p.get("service_id", "")))
        return None if view is None else view.state in set(p.get("states", []))

    async def _attributes(ctx: LeafContext) -> Any | None:
        if ctx.event is None:
            return None
        for registration in capabilities.system_providers(ACTIVITY):
            provider = registration.provider
            if provider.handles(ctx.event.type):
                return await asyncio.wait_for(provider.attributes(ctx.event.type, dict(ctx.event.payload)), 2)
        return None

    def _norm(values: Any) -> set[str]:
        return {normalize_for_search(str(v), None) for v in values or []}

    async def media_kind(ctx: LeafContext, p: Mapping[str, Any]) -> bool | None:
        attributes = await _attributes(ctx)
        if attributes is None or attributes.media_kind is None:
            return None
        return normalize_for_search(attributes.media_kind, None) in _norm(p.get("kinds"))

    async def genre(ctx: LeafContext, p: Mapping[str, Any]) -> bool | None:
        attributes = await _attributes(ctx)
        if attributes is None or not attributes.genres:
            return None
        return bool(_norm(attributes.genres) & _norm(p.get("genres")))

    async def title_contains(ctx: LeafContext, p: Mapping[str, Any]) -> bool | None:
        attributes = await _attributes(ctx)
        titles = [
            t for t in (getattr(attributes, "title", None), getattr(attributes, "original_title", None)) if t
        ]
        if not titles:
            return None
        return any(f in normalize_for_search(t, None) for f in _norm(p.get("texts")) for t in titles)

    async def campaign_active(ctx: LeafContext, p: Mapping[str, Any]) -> bool | None:
        reader = _provider(capabilities, CAMPAIGNS)
        if reader is None:
            return None
        return bool(await reader.is_active(str(p.get("campaign", "")), ctx.at))

    async def time_window(ctx: LeafContext, p: Mapping[str, Any]) -> bool | None:
        try:
            zone = ZoneInfo(str(p.get("timezone", "UTC")))
            start, end = time.fromisoformat(str(p["start"])), time.fromisoformat(str(p["end"]))
        except (ZoneInfoNotFoundError, KeyError, ValueError):
            return None
        local = ctx.at.astimezone(zone)
        days = p.get("weekdays")
        if days and local.weekday() not in set(days):
            return False
        now = local.time()
        return start <= now < end if start <= end else (now >= start or now < end)

    async def permission_held(ctx: LeafContext, p: Mapping[str, Any]) -> bool | None:
        if ctx.subject_user is None:
            return None
        return await authorizer.is_allowed(Principal(user_id=ctx.subject_user), str(p.get("permission", "")))

    async def event_field(ctx: LeafContext, p: Mapping[str, Any]) -> bool | None:
        if ctx.event is None:
            return None
        return compare(ctx.event.payload.get(str(p.get("field"))), str(p.get("op", "eq")), p.get("value"))

    for key, evaluate, schema, description in (
        (
            "user_is",
            user_is,
            {"users": "list[uuid]"},
            "The trigger's user is one of these users",
        ),
        ("role_in", role_in, {"roles": "list[string]"}, "The trigger's user holds one of these roles"),
        ("level_at_least", level_at_least, {"level": "integer"}, "The trigger's user reached this level"),
        (
            "service_state_in",
            service_state_in,
            {"service_id": "string", "states": "list[string]"},
            "A service is in one of these states",
        ),
        ("media_kind", media_kind, {"kinds": "list[string]"}, "The media is of one of these kinds"),
        ("genre", genre, {"genres": "list[string]"}, "The media has one of these genres"),
        (
            "title_contains",
            title_contains,
            {"texts": "list[string]"},
            "The title contains one of these texts",
        ),
        ("campaign_active", campaign_active, {"campaign": "string"}, "A campaign is active"),
        (
            "time_window",
            time_window,
            {"start": "HH:MM", "end": "HH:MM", "timezone": "string", "weekdays": "list[integer]?"},
            "Now is within a time window",
        ),
        (
            "permission_held",
            permission_held,
            {"permission": "string"},
            "The trigger's user holds a permission (informational)",
        ),
        (
            "event_field",
            event_field,
            {"field": "string", "op": "eq|ne|in|contains|gt|gte|lt|lte", "value": "any"},
            "A declared attribute of the event compares to a value",
        ),
    ):
        if registry.get(key) is None:
            registry.register(ConditionLeaf(key, description, evaluate, schema, OWNER))
