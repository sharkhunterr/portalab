"""Automation definition (T004; R1-R3): a **closed** bounded model — one trigger, a condition tree (``all_of``
/ ``any_of`` / ``not`` over closed leaves, depth ≤ 3) and ≤ N sequential steps with ``on_error``. No
branching, loops, scripts or cron strings; parameters only use ``${…}`` substitution of declared values."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

IDENT = r"^[a-z][a-z0-9_]{0,63}$"
EVENT_TYPE = r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$"
MAX_DEPTH = 3


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FieldFilter(_Closed):
    field: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    op: Literal["eq", "ne", "in", "gt", "gte", "lt", "lte", "contains"] = "eq"
    value: str | int | float | bool | list[str | int | float]


class Schedule(_Closed):
    frequency: Literal["daily", "weekly", "monthly"]
    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    weekday: int | None = Field(default=None, ge=0, le=6)  # weekly: 0 = Monday
    day: int | None = Field(default=None, ge=1, le=28)  # monthly

    @model_validator(mode="after")
    def _anchor(self) -> "Schedule":
        if self.frequency == "weekly" and self.weekday is None:
            raise ValueError("weekly schedules need a weekday")
        if self.frequency == "monthly" and self.day is None:
            raise ValueError("monthly schedules need a day (1-28)")
        return self


class Trigger(_Closed):
    kind: Literal["event", "at", "relative", "recurring"]
    event_type: str | None = Field(default=None, pattern=EVENT_TYPE, max_length=128)
    filter: list[FieldFilter] = Field(default_factory=list, max_length=10)
    reference: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{0,63}$")  # relative: datetime field
    offset_minutes: int = Field(default=0, ge=-10_080, le=10_080)
    at: datetime | None = None
    schedule: Schedule | None = None
    timezone: str = "UTC"

    @model_validator(mode="after")
    def _shape(self) -> "Trigger":
        needs = {
            "event": ("event_type",),
            "relative": ("event_type", "reference"),
            "at": ("at",),
            "recurring": ("schedule",),
        }[self.kind]
        missing = [name for name in needs if getattr(self, name) is None]
        if missing:
            raise ValueError(f"a {self.kind} trigger needs {', '.join(missing)}")
        if self.at is not None and self.at.tzinfo is None:
            raise ValueError("'at' needs a time zone offset")
        return self


class Node(_Closed):
    all_of: list["Node"] | None = Field(default=None, max_length=20)
    any_of: list["Node"] | None = Field(default=None, max_length=20)
    not_: "Node | None" = Field(default=None, alias="not")
    leaf: str | None = Field(default=None, pattern=IDENT)
    params: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    @model_validator(mode="after")
    def _one(self) -> "Node":
        chosen = [n for n in ("all_of", "any_of", "not_", "leaf") if getattr(self, n) is not None]
        if len(chosen) != 1:
            raise ValueError("a condition node is exactly one of all_of, any_of, not, leaf")
        if self.params and self.leaf is None:
            raise ValueError("only leaves take params")
        return self

    def depth(self) -> int:
        if self.leaf is not None:
            return 0
        children = self.all_of or self.any_of or ([self.not_] if self.not_ else [])
        return 1 + max((c.depth() for c in children), default=0)

    def leaves(self) -> list["Node"]:
        if self.leaf is not None:
            return [self]
        children = self.all_of or self.any_of or ([self.not_] if self.not_ else [])
        return [leaf for c in children for leaf in c.leaves()]


class Step(_Closed):
    id: str = Field(pattern=IDENT)
    action: str = Field(pattern=r"^(plugin:)?[a-z][a-z0-9_-]*(\.[a-z][a-z0-9_]*)+$", max_length=128)
    params: dict[str, Any] = Field(default_factory=dict)
    on_error: Literal["stop", "continue"] = "stop"


class Limits(_Closed):
    cooldown_s: int = Field(default=0, ge=0, le=30 * 86400)
    dedup_key: str | None = Field(default=None, max_length=200)
    dedup_window_s: int = Field(default=0, ge=0, le=30 * 86400)
    batchable: bool = False
    rate_per_min: int | None = Field(default=None, ge=1, le=10_000)


class Identity(_Closed):
    kind: Literal["author", "system"] = "author"
    scopes: list[str] = Field(default_factory=list, max_length=20)


class Definition(_Closed):
    name: str = Field(min_length=1, max_length=120)
    trigger: Trigger
    conditions: Node | None = None
    steps: list[Step] = Field(min_length=1, max_length=50)
    limits: Limits = Limits()
    identity: Identity = Identity()
    schema_version: Literal[1] = 1

    @field_validator("steps")
    @classmethod
    def _unique(cls, steps: list[Step]) -> list[Step]:
        ids = [s.id for s in steps]
        if len(set(ids)) != len(ids):
            raise ValueError("step ids must be unique")
        return steps

    @model_validator(mode="after")
    def _depth(self) -> "Definition":
        if self.conditions is not None and self.conditions.depth() > MAX_DEPTH:
            raise ValueError(f"conditions nest at most {MAX_DEPTH} levels")
        return self
