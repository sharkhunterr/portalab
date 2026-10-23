"""Reward rule definition (T012/T014; R2): a **closed** record — never a generic rules engine.

``{event_type, predicate[], grants[], multiplier, limits{cooldown_seconds, caps[], diminishing}}``:
predicates and per-unit fields may only use attributes the event type declares ``rewardable`` (007);
grants are a fixed amount, ``per_unit(field, factor, max)`` or both (027: e.g. 10 XP per play
plus 1 XP per minute watched); rules can only produce ledger grants — and (issue 234) boosters of the
event's content (a film, a season), given once per member and content by the cards."""

from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from portalab.capabilities.events import EventTypeRegistry
from portalab.core.errors import ValidationFailed
from portalab.modules.gamification.events import OWN_TYPES

FIELD = r"^[a-z][a-z0-9_]{0,63}$"
Scalar = str | int | float | bool


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    field: str = Field(pattern=FIELD)
    op: Literal["eq", "ne", "in", "gt", "gte", "lt", "lte"] = "eq"
    value: Scalar | list[Scalar]


class PerUnit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    field: str = Field(pattern=FIELD)
    factor: float = Field(gt=0, le=1_000_000)
    max: int | None = Field(default=None, ge=1, le=1_000_000_000)


class Grant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    value: Literal["xp", "contribution", "coins"]
    amount: int | None = Field(default=None, ge=1, le=1_000_000_000)
    per_unit: PerUnit | None = None

    @model_validator(mode="after")
    def _one(self) -> "Grant":
        if self.amount is None and self.per_unit is None:
            raise ValueError("a grant has an amount, a per_unit formula or both")
        return self


class Cap(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    period: Literal["hour", "day", "week"]
    max_amount: int = Field(ge=0, le=1_000_000_000)
    value: Literal["xp", "contribution", "coins"] | None = None  # None: every value of the rule


class Diminishing(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["geometric", "steps"]
    period: Literal["hour", "day", "week"] = "day"
    factor: float = Field(default=0.5, gt=0, lt=1)  # geometric: amount · factor^repeats
    steps: list[float] = Field(default_factory=list, max_length=20)  # steps: amount · steps[repeats]

    @model_validator(mode="after")
    def _steps(self) -> "Diminishing":
        if self.kind == "steps" and (not self.steps or any(not 0 <= s <= 1 for s in self.steps)):
            raise ValueError("steps are factors between 0 and 1")
        return self


class Limits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    cooldown_seconds: int = Field(default=0, ge=0, le=30 * 86400)
    caps: list[Cap] = Field(default_factory=list, max_length=10)
    diminishing: Diminishing | None = None


class RuleDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    event_type: str = Field(pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$", max_length=128)
    predicate: list[Condition] = Field(default_factory=list, max_length=10)
    grants: list[Grant] = Field(default_factory=list, max_length=3)
    # issue 234: boosters of the event's content (its ``object``: a film, a season), once per member and
    # content
    boosters: int = Field(default=0, ge=0, le=3)
    multiplier: float = Field(default=1.0, gt=0, le=100)
    limits: Limits = Limits()
    label: str = Field(default="", max_length=120)

    @model_validator(mode="after")
    def _gives(self) -> "RuleDefinition":
        if not self.grants and not self.boosters:
            raise ValueError("a rule gives something: grants, boosters or both")
        return self

    def fields(self) -> set[str]:
        used = {c.field for c in self.predicate}
        used |= {g.per_unit.field for g in self.grants if g.per_unit}
        return used


def parse_rule(raw: Mapping[str, Any], types: EventTypeRegistry | None = None) -> RuleDefinition:
    try:
        rule = RuleDefinition.model_validate(dict(raw))
    except ValidationError as exc:
        raise ValidationFailed(
            "This rule is not valid.",
            code="economy.rule_invalid",
            extensions={"errors": [e["msg"][:200] for e in exc.errors()][:10]},
        ) from exc
    if rule.event_type in OWN_TYPES:
        raise ValidationFailed("Rules cannot react to economy events.", code="economy.rule_invalid")
    if len({g.value for g in rule.grants}) != len(rule.grants):
        raise ValidationFailed("One grant per value.", code="economy.rule_invalid")
    if types is not None:
        event_type = types.get(rule.event_type)
        if event_type is None:
            raise ValidationFailed("Unknown event type.", code="economy.rule_invalid")
        unknown = sorted(rule.fields() - set(event_type.rewardable))
        if unknown:
            raise ValidationFailed(
                "Rules may only use rewardable event attributes.",
                code="economy.rule_invalid",
                extensions={"fields": unknown},
            )
        if rule.boosters and (event_type.schema is None or "object" not in event_type.schema.model_fields):
            raise ValidationFailed(
                "Only an action about a content gives its boosters.", code="economy.rule_invalid"
            )
    return rule


def _compare(actual: Any, op: str, expected: Any) -> bool:
    try:
        match op:
            case "eq":
                return bool(actual == expected)
            case "ne":
                return bool(actual != expected)
            case "in":
                return actual in (expected if isinstance(expected, list) else [expected])
            case "gt":
                return bool(actual > expected)
            case "gte":
                return bool(actual >= expected)
            case "lt":
                return bool(actual < expected)
            case "lte":
                return bool(actual <= expected)
    except TypeError:
        return False
    return False


def matches(conditions: Iterable[Condition], payload: Mapping[str, Any]) -> bool:
    return all(c.field in payload and _compare(payload[c.field], c.op, c.value) for c in conditions)
