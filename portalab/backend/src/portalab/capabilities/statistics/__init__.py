"""Statistics contracts (spec 017 T006; contracts/statistics-contracts.md).

* ``StatisticDefinition`` — a **closed-set declarative document** (no query or expression language):
  measures ``count|sum|avg|min|max|distinct_count``, filters/dimensions over fields the 007 event registry
  marks ``aggregatable`` (plus the envelope fields ``actor``, ``subject``, ``source``), a scope, period
  options, a visualization type, privacy threshold and an optional unlock condition tree;
* ``StatisticsProvider`` — the single authoritative read path (``get``/``catalog``), always bounded by the
  viewer's permissions, privacy and unlocks; every consumer (dashboard, gamification, campaigns, Wrapped,
  AI tools, leaderboards) gets the same value for the same inputs;
* definition packs — modules and plugins contribute definitions (owner-tagged; plugin packs install
  inactive until the Admin enables them);
* ports consumed for unlock conditions: ``ProgressionReader`` (013), ``EntitlementReader`` (015, declared
  by the dashboard SDK), ``CampaignReader`` (014).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from portalab.capabilities.registry import CapabilitySpec
from portalab.core.authz_port import Principal

PROVIDER = "statistics.provider"
PROGRESSION = "gamification.progression"
CAMPAIGNS = "campaigns.reader"

ENVELOPE_FIELDS: frozenset[str] = frozenset({"actor", "subject", "source"})
MeasureKind = Literal["count", "sum", "avg", "min", "max", "distinct_count"]
Scope = Literal["personal", "community", "global"]
PeriodKind = Literal["day", "week", "month", "quarter", "year", "last_n_days", "custom"]
StatState = Literal["available", "partial", "stale", "locked", "unavailable", "insufficient_data", "no_data"]
_FIELD = r"^[a-z][a-z0-9_]{0,63}$"


class Measure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: MeasureKind
    field: str | None = Field(
        default=None, pattern=_FIELD
    )  # sum/avg/min/max: numeric field; distinct: subject


class FilterClause(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    field: str = Field(pattern=_FIELD)
    op: Literal["eq", "ne", "in", "gt", "gte", "lt", "lte"] = "eq"
    value: str | int | float | bool | list[str | int | float]


class UnlockCondition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal[
        "level_at_least", "achievement_earned", "product_owned", "campaign_active", "all_of", "any_of"
    ]
    value: str | int | None = None
    conditions: tuple["UnlockCondition", ...] = ()


class Unlock(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    condition: UnlockCondition
    relock: bool | None = None  # default: true for campaign/product, false for level/achievement
    hint_key: str | None = Field(default=None, max_length=128)


class Visualization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    type: Literal["line", "bar", "area", "pie", "number", "table"] = "line"
    options: dict[str, str | int | bool] = Field(default_factory=dict)


class StatisticDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    key: str = Field(pattern=r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$", max_length=96)
    title_key: str = Field(min_length=1, max_length=128)
    description_key: str | None = Field(default=None, max_length=128)
    domain: str = Field(pattern=_FIELD)
    scope: Scope = "community"
    event_types: tuple[str, ...] = Field(min_length=1, max_length=10)
    filter: tuple[FilterClause, ...] = ()
    measure: Measure
    dimensions: tuple[str, ...] = Field(default=(), max_length=2)
    granularity: Literal["day"] = "day"
    period_options: tuple[PeriodKind, ...] = ("day", "week", "month", "quarter", "year", "last_n_days")
    viz: Visualization = Visualization()
    hideable: bool = True
    required_permission: str = Field(default="statistics.read", min_length=3, max_length=128)
    min_cohort_size: int | None = Field(default=None, ge=1, le=1000)
    unlock: Unlock | None = None
    sources: tuple[str, ...] = ()  # service ids the statistic depends on (partial/stale states)
    stale_after_s: int | None = Field(default=None, ge=60, le=7 * 86400)
    schema_version: Literal[1] = 1

    @field_validator("dimensions")
    @classmethod
    def _dimensions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        import re

        for name in value:
            if not re.fullmatch(_FIELD, name):
                raise ValueError(f"invalid dimension {name!r}")
        return value

    def fields(self) -> set[str]:
        used = {clause.field for clause in self.filter} | set(self.dimensions)
        if self.measure.field:
            used.add(self.measure.field)
        return used


class DefinitionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Period:
    kind: PeriodKind
    start: date | None = None  # custom
    end: date | None = None  # custom (inclusive)
    days: int | None = None  # last_n_days
    anchor: date | None = None  # a day inside the wanted day/week/month/…; default: today


@dataclass(frozen=True, slots=True)
class Trend:
    delta: float
    direction: Literal["up", "down", "flat"]
    previous_value: float
    percent: float | None  # None when the previous period is empty (no misleading percentage)


@dataclass(frozen=True, slots=True)
class StatResult:
    key: str
    state: StatState
    definition_version: int | None = None
    as_of: datetime | None = None
    value: float | None = None
    series: Sequence[Mapping[str, Any]] = ()  # [{"day": "2026-10-01", "value": 3, "dims": {...}}]
    breakdown: Sequence[Mapping[str, Any]] = ()  # [{"dims": {...}, "value": 3}] (small cells suppressed)
    trend: Trend | None = None
    unlock_hint: str | None = None
    source_states: Mapping[str, str] = field(default_factory=dict)
    period_start: date | None = None
    period_end: date | None = None


@dataclass(frozen=True, slots=True)
class SubjectRef:
    kind: Literal["user", "community"]
    id: UUID | None = None


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    key: str
    title_key: str
    description_key: str | None
    domain: str
    scope: str
    viz: str
    hideable: bool
    locked: bool
    unlock_hint: str | None
    period_options: tuple[str, ...]


@runtime_checkable
class StatisticsProvider(Protocol):
    async def get(
        self,
        stat_key: str,
        *,
        viewer: Principal,
        subject: SubjectRef | None = None,
        period: Period | None = None,  # default: the last 30 days
        filters: Mapping[str, str] | None = None,
    ) -> StatResult: ...

    async def catalog(self, viewer: Principal) -> Sequence[CatalogEntry]: ...


@runtime_checkable
class ProgressionReader(Protocol):
    async def level(self, user_id: UUID) -> int: ...

    async def has_achievement(self, user_id: UUID, achievement: str) -> bool: ...


@runtime_checkable
class CampaignReader(Protocol):
    async def is_active(self, campaign: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class _Pack:
    owner: str
    domain: str
    definitions: tuple[StatisticDefinition, ...]
    active: bool


class PackRegistry:
    """Definition packs, owner-tagged (F20). Plugin packs are registered inactive (the Admin enables them)."""

    def __init__(self) -> None:
        self._packs: dict[tuple[str, str], _Pack] = {}

    def register(
        self, domain: str, definitions: Sequence[StatisticDefinition | Mapping[str, Any]], *, owner: str
    ) -> list[StatisticDefinition]:
        parsed = [
            d if isinstance(d, StatisticDefinition) else StatisticDefinition.model_validate(d)
            for d in definitions
        ]
        plugin = owner.startswith("plugin:")
        for definition in parsed:
            if plugin and not definition.key.startswith(
                f"plugin_{owner.removeprefix('plugin:').replace('-', '_')}."
            ):
                raise DefinitionError(
                    f"plugin statistics are namespaced 'plugin_<key>.' ({definition.key!r})"
                )
        self._packs[(owner, domain)] = _Pack(owner, domain, tuple(parsed), active=not plugin)
        return parsed

    def packs(self) -> list[tuple[str, str, tuple[StatisticDefinition, ...], bool]]:
        return [(p.owner, p.domain, p.definitions, p.active) for _, p in sorted(self._packs.items())]

    def definitions(self) -> list[tuple[StatisticDefinition, str, bool]]:
        return [(d, p.owner, p.active) for p in self._packs.values() for d in p.definitions]

    def unregister(self, owner: str) -> int:
        doomed = [key for key, pack in self._packs.items() if pack.owner == owner]
        for key in doomed:
            del self._packs[key]
        return len(doomed)


default_packs = PackRegistry()


def register_definition_pack(
    domain: str, definitions: Sequence[StatisticDefinition | Mapping[str, Any]], *, owner: str
) -> list[StatisticDefinition]:
    return default_packs.register(domain, definitions, owner=owner)


def _spec(name: str, protocol: type[Any], description: str) -> CapabilitySpec:
    return CapabilitySpec(
        name=name, version="1.0", protocol=protocol, multi_provider=False, description=description
    )


SPECS: tuple[CapabilitySpec, ...] = (
    _spec(PROVIDER, StatisticsProvider, "Authoritative statistics read path (017)"),
    _spec(PROGRESSION, ProgressionReader, "User level and achievements (Gamification 013)"),
    _spec(CAMPAIGNS, CampaignReader, "Active campaigns (Campaigns 014)"),
)
