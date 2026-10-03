"""Dashboard & widget SDK (spec 009 T006; contracts/dashboard-contracts.md). The dashboard module owns
composition only; domain modules (and plugins, declaratively) register:

* a ``WidgetDefinition`` (key, permission, config JSON Schema, sizes, refresh hints, closed-set conditions,
  frontend component or declarative template) with a ``WidgetDataProvider`` that authorizes, applies
  visibility and returns a ``WidgetPayload`` (functional state + data);
* optionally a ``ChangeSummaryProvider`` for "Since Last Login" (permission and privacy at source).

Registrations are owner-tagged: ``unregister_owner(owner)`` removes everything a disabled plugin
contributed; stored user instances are kept (placeholder, restored on reactivation).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import UUID

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.registry import CapabilitySpec
from portalab.core.authz_port import Principal

ENTITLEMENTS = "marketplace.entitlements"

WidgetState = Literal["available", "partial", "stale", "unavailable", "error", "unauthorized", "no-data"]
ConditionType = Literal[
    "role_in", "permission", "service_state", "campaign_active", "module_enabled", "data_present"
]
CONDITION_TYPES: tuple[str, ...] = (
    "role_in",
    "permission",
    "service_state",
    "campaign_active",
    "module_enabled",
    "data_present",
)
TEMPLATES: tuple[str, ...] = ("stat", "list", "chart", "timeline", "status")
_KEY_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_.-:")


@dataclass(frozen=True, slots=True)
class Size:
    w: int
    h: int


@dataclass(frozen=True, slots=True)
class SizeLimits:
    default: Size = Size(4, 2)
    min: Size = Size(2, 1)
    max: Size = Size(12, 6)

    def clamp(self, w: int, h: int) -> Size:
        return Size(max(self.min.w, min(self.max.w, w)), max(self.min.h, min(self.max.h, h)))


@dataclass(frozen=True, slots=True)
class Refresh:
    mode: Literal["on_view", "interval", "event"] = "on_view"
    interval_s: int | None = None
    events: tuple[str, ...] = ()  # event types that invalidate this widget (SSE ``widget.invalidate``)


@dataclass(frozen=True, slots=True)
class Condition:
    """A closed-set condition (no free-form expressions — never a second rules engine)."""

    type: str
    value: Any = None


@dataclass(frozen=True, slots=True)
class WidgetDefinition:
    key: str  # plugins: "plugin:<key>.<widget>"
    owner: str
    title_key: str
    required_permission: str
    description_key: str | None = None
    icon: str | None = None
    config_schema: Mapping[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})
    config_defaults: Mapping[str, Any] = field(default_factory=dict)
    size: SizeLimits = SizeLimits()
    multiple: bool = False
    refresh: Refresh = Refresh()
    stale_after_s: int | None = None
    conditions: tuple[Condition, ...] = ()
    template: str | None = None  # declarative widgets (marketplace/plugins)
    component_id: str | None = None  # first-party frontend component
    schema_version: int = 1
    product: str | None = None  # marketplace widget product (entitlement-gated, 015)


@dataclass(frozen=True, slots=True)
class WidgetPayload:
    state: WidgetState
    as_of: datetime | None = None
    stale_after_s: int | None = None
    data: Mapping[str, Any] | None = None
    partial_reasons: tuple[str, ...] = ()
    config_invalid: bool = False


class WidgetUnavailable(Exception):
    """Raised by a provider when its backing source cannot answer (→ ``unavailable`` state)."""


class WidgetUnauthorized(Exception):
    """Raised by a provider when the principal may not see this widget's data (→ ``unauthorized``)."""


@runtime_checkable
class WidgetDataProvider(Protocol):
    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload: ...


@dataclass(frozen=True, slots=True)
class ChangeItem:
    kind: str
    occurred_at: datetime
    ref: str  # SPA route or ``portalab://kind/id``
    title: str | None = None  # already-localized text, or
    title_key: str | None = None  # a catalog key (with ``title_args``)
    title_args: Mapping[str, Any] = field(default_factory=dict)
    priority: int = 0  # higher first


@runtime_checkable
class ChangeSummaryProvider(Protocol):
    kind: str

    async def changes_since(
        self, principal: Principal, since: datetime, limit: int, ctx: LocaleContext
    ) -> Sequence[ChangeItem]: ...


@runtime_checkable
class EntitlementReader(Protocol):
    """015 port (stub until Marketplace): does the user own a widget product?"""

    async def owns(self, user_id: UUID, product: str) -> bool: ...


class WidgetRegistryError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RegisteredWidget:
    definition: WidgetDefinition
    provider: WidgetDataProvider
    owner: str


def validate_definition(definition: WidgetDefinition, owner: str) -> None:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError

    key = definition.key
    if not key or len(key) > 96 or not set(key) <= _KEY_CHARS or "." not in key:
        raise WidgetRegistryError(f"invalid widget key {key!r}")
    if owner.startswith("plugin:") and not key.startswith(f"plugin:{owner.removeprefix('plugin:')}."):
        raise WidgetRegistryError(f"plugin widget keys are namespaced 'plugin:<key>.' ({key!r})")
    if definition.template is not None and definition.template not in TEMPLATES:
        raise WidgetRegistryError(f"unknown template {definition.template!r}")
    if owner.startswith("plugin:") and definition.template is None:
        raise WidgetRegistryError("plugin widgets are declarative (a standard template is required)")
    for condition in definition.conditions:
        if condition.type not in CONDITION_TYPES:
            raise WidgetRegistryError(f"unknown condition {condition.type!r}")
    limits = definition.size
    if not (
        1 <= limits.min.w <= limits.default.w <= limits.max.w <= 12
        and 1 <= limits.min.h <= limits.default.h <= limits.max.h
    ):
        raise WidgetRegistryError("inconsistent size limits")
    try:
        Draft202012Validator.check_schema(dict(definition.config_schema))
    except SchemaError as exc:
        raise WidgetRegistryError(f"invalid config schema: {exc.message}") from exc
    errors = list(
        Draft202012Validator(dict(definition.config_schema)).iter_errors(dict(definition.config_defaults))
    )
    if errors:
        raise WidgetRegistryError(f"config defaults do not match the schema: {errors[0].message}")


class WidgetRegistry:
    """In-memory registry of widgets and summary providers, owner-tagged (F20)."""

    def __init__(self) -> None:
        self._widgets: dict[str, RegisteredWidget] = {}
        self._summaries: dict[str, tuple[str, ChangeSummaryProvider]] = {}

    def register(
        self, definition: WidgetDefinition, provider: WidgetDataProvider, *, owner: str | None = None
    ) -> None:
        owner = owner or definition.owner
        validate_definition(definition, owner)
        existing = self._widgets.get(definition.key)
        if existing is not None and existing.owner != owner:
            raise WidgetRegistryError(f"widget {definition.key!r} is already registered by {existing.owner}")
        self._widgets[definition.key] = RegisteredWidget(definition, provider, owner)

    def unregister(self, key: str) -> bool:
        return self._widgets.pop(key, None) is not None

    def register_summary(self, provider: ChangeSummaryProvider, *, owner: str) -> None:
        self._summaries[provider.kind] = (owner, provider)

    def get(self, key: str) -> RegisteredWidget | None:
        return self._widgets.get(key)

    def widgets(self) -> list[RegisteredWidget]:
        return [self._widgets[key] for key in sorted(self._widgets)]

    def summaries(self) -> list[ChangeSummaryProvider]:
        return [provider for _, (_, provider) in sorted(self._summaries.items())]

    def unregister_owner(self, owner: str) -> int:
        widgets = [key for key, entry in self._widgets.items() if entry.owner == owner]
        summaries = [kind for kind, (who, _) in self._summaries.items() if who == owner]
        for key in widgets:
            del self._widgets[key]
        for kind in summaries:
            del self._summaries[kind]
        return len(widgets) + len(summaries)


default_widgets = WidgetRegistry()


def register_widget(
    definition: WidgetDefinition, provider: WidgetDataProvider, *, owner: str | None = None
) -> None:
    default_widgets.register(definition, provider, owner=owner)


def unregister_widget(key: str) -> bool:
    return default_widgets.unregister(key)


ENTITLEMENTS_SPEC = CapabilitySpec(
    name=ENTITLEMENTS,
    version="1.0",
    protocol=EntitlementReader,
    multi_provider=False,
    description="Marketplace entitlements: does a user own a product (widget products, spec 015).",
)
SPECS: tuple[CapabilitySpec, ...] = (ENTITLEMENTS_SPEC,)
