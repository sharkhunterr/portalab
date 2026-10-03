"""Test doubles for widgets."""

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from portalab.capabilities.dashboard import (
    Condition,
    Size,
    SizeLimits,
    WidgetDefinition,
    WidgetPayload,
    WidgetUnauthorized,
    WidgetUnavailable,
)
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Principal, ResourceRef

NOW = datetime(2026, 10, 5, 12, tzinfo=UTC)


def definition(key: str, **kw: Any) -> WidgetDefinition:
    values: dict[str, Any] = {
        "owner": "module:test",
        "title_key": f"t:{key}",
        "required_permission": "users.self.manage",
        "config_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 10}},
            "additionalProperties": False,
        },
        "config_defaults": {"limit": 5},
        "size": SizeLimits(default=Size(4, 2), min=Size(2, 1), max=Size(8, 4)),
    }
    values.update(kw)
    conditions = values.pop("conditions", ())
    return WidgetDefinition(
        key=key, conditions=tuple(Condition(**c) if isinstance(c, dict) else c for c in conditions), **values
    )


class FakeWidget:
    def __init__(self, mode: str = "ok", *, as_of: datetime = NOW, delay: float = 0.0) -> None:
        self.mode = mode
        self.as_of = as_of
        self.delay = delay
        self.calls = 0
        self.last_config: Mapping[str, Any] | None = None

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        self.calls += 1
        self.last_config = config
        if self.delay:
            await asyncio.sleep(self.delay)
        match self.mode:
            case "unavailable":
                raise WidgetUnavailable("down")
            case "unauthorized":
                raise WidgetUnauthorized()
            case "crash":
                raise RuntimeError("boom")
            case "partial":
                return WidgetPayload(
                    "partial", as_of=self.as_of, data={"n": 1}, partial_reasons=("one source down",)
                )
            case "empty":
                return WidgetPayload("no-data", as_of=self.as_of)
        return WidgetPayload("available", as_of=self.as_of, data={"n": 3, "config": dict(config)})


class Authorizer:
    def __init__(self, allowed: set[str] | None = None) -> None:
        self.allowed = allowed if allowed is not None else {"users.self.manage"}

    async def is_allowed(
        self, principal: Principal, permission: str, resource: ResourceRef | None = None
    ) -> bool:
        return permission in self.allowed
