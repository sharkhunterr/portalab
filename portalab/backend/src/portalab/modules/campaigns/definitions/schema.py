"""Campaign definition (T004/T007; R3, R5): a **closed** record — unknown fields, operators or expressions
are rejected; sizes are bounded. Schedules are wall-clock times in the campaign's time zone; modifiers are
``{id, value, factor, when}`` over a closed condition catalog (AND semantics inside a modifier)."""

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from portalab.core.errors import ValidationFailed

SCHEMA_VERSION = 1
IDENT = r"^[a-z0-9][a-z0-9_-]{0,63}$"


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Recurrence(_Closed):
    kind: Literal["none", "yearly", "custom"] = "none"
    every: int = Field(default=1, ge=1, le=366)
    unit: Literal["days", "weeks", "months"] = "weeks"
    count: int = Field(default=5, ge=1, le=50)  # occurrences materialized ahead


class Schedule(_Closed):
    start_at: datetime  # wall clock in the campaign time zone (no offset)
    end_at: datetime | None = None
    duration_hours: int | None = Field(default=None, ge=1, le=24 * 366)
    recurrence: Recurrence = Recurrence()

    @field_validator("start_at", "end_at")
    @classmethod
    def _wall_clock(cls, value: datetime | None) -> datetime | None:
        return None if value is None else value.replace(tzinfo=None)

    @model_validator(mode="after")
    def _window(self) -> "Schedule":
        if (self.end_at is None) == (self.duration_hours is None):
            raise ValueError("give either end_at or duration_hours")
        if self.end_at is not None and self.end_at <= self.start_at:
            raise ValueError("end_at must follow start_at")
        return self


class Audience(_Closed):
    kind: Literal["all", "roles", "users", "level_range"] = "all"
    roles: list[str] = Field(default_factory=list, max_length=20)
    users: list[str] = Field(default_factory=list, max_length=500)
    min_level: int | None = Field(default=None, ge=1, le=1000)
    max_level: int | None = Field(default=None, ge=1, le=1000)


class When(_Closed):
    media_kind: list[str] = Field(default_factory=list, max_length=20)
    genre: list[str] = Field(default_factory=list, max_length=50)
    title_contains: list[str] = Field(default_factory=list, max_length=20)
    activity: list[str] = Field(default_factory=list, max_length=20)
    audience: Audience = Audience()

    @field_validator("title_contains", "genre", "media_kind")
    @classmethod
    def _short(cls, values: list[str]) -> list[str]:
        if any(not 1 <= len(v) <= 100 for v in values):
            raise ValueError("condition values are 1-100 characters")
        return values


class ModifierDef(_Closed):
    id: str = Field(pattern=IDENT)
    value: Literal["xp", "contribution", "coins"]
    factor: float = Field(gt=0, le=10)
    when: When = When()


class DiscountDef(_Closed):
    """027: a shop reduction while the campaign is active — on named products and/or whole categories."""

    id: str = Field(pattern=IDENT)
    percent: int = Field(ge=1, le=90)
    products: list[str] = Field(default_factory=list, max_length=200)
    categories: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _targets(self) -> "DiscountDef":
        if not self.products and not self.categories:
            raise ValueError("a discount names products or categories")
        if any(not 1 <= len(v) <= 96 for v in [*self.products, *self.categories]):
            raise ValueError("product and category keys are 1-96 characters")
        return self


class Theme(_Closed):
    theme_key: str = Field(min_length=1, max_length=64)
    presentation_priority: int = Field(default=0, ge=0, le=100)


MAX_NESTED_BYTES = 16_000
MAX_DEPTH = 8


def _depth(value: Any, level: int = 0) -> int:
    if isinstance(value, dict):
        return max((_depth(v, level + 1) for v in value.values()), default=level + 1)
    if isinstance(value, list):
        return max((_depth(v, level + 1) for v in value), default=level + 1)
    return level


class Nested(_Closed):
    key: str = Field(pattern=IDENT)
    definition: dict[str, Any]

    @field_validator("definition")
    @classmethod
    def _bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, default=str)) > MAX_NESTED_BYTES or _depth(value) > MAX_DEPTH:
            raise ValueError("nested definitions are limited in size and depth")
        return value


class CampaignDefinition(_Closed):
    names: dict[str, str] = Field(min_length=1, max_length=10)
    description: str = Field(default="", max_length=2000)
    timezone: str = "UTC"
    schedule: Schedule
    modifiers: list[ModifierDef] = Field(default_factory=list, max_length=20)
    discounts: list[DiscountDef] = Field(default_factory=list, max_length=20)
    achievements: list[Nested] = Field(default_factory=list, max_length=10)
    quests: list[Nested] = Field(default_factory=list, max_length=10)
    theme: Theme | None = None
    ending_soon_hours: int | None = Field(default=None, ge=1, le=24 * 30)
    schema_version: Literal[1] = 1

    @field_validator("names")
    @classmethod
    def _names(cls, names: dict[str, str]) -> dict[str, str]:
        if any(not 1 <= len(v) <= 120 or not 2 <= len(k) <= 10 for k, v in names.items()):
            raise ValueError("names are 1-120 characters per language code")
        return names

    @field_validator("timezone")
    @classmethod
    def _zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("unknown time zone") from exc
        return value

    @model_validator(mode="after")
    def _unique(self) -> "CampaignDefinition":
        ids = [m.id for m in self.modifiers]
        if len(set(ids)) != len(ids):
            raise ValueError("modifier ids must be unique")
        discounts = [d.id for d in self.discounts]
        if len(set(discounts)) != len(discounts):
            raise ValueError("discount ids must be unique")
        return self

    def name(self, language: str = "en") -> str:
        return self.names.get(language) or self.names.get("en") or next(iter(self.names.values()))


def parse_definition(raw: Mapping[str, Any]) -> CampaignDefinition:
    try:
        return CampaignDefinition.model_validate(dict(raw))
    except ValidationError as exc:
        raise ValidationFailed(
            "This campaign definition is not valid.",
            code="campaign.invalid_definition",
            extensions={
                "errors": [f"{'.'.join(map(str, e['loc']))}: {e['msg']}"[:200] for e in exc.errors()][:20]
            },
        ) from exc
