"""Household rules (spec 032): the kinds' presets, the restrictions as stored, PINs and colours."""

import re
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from portalab.capabilities.household import AGES, FEATURES, GENRES, SCREEN_MINUTES, TYPES, Mode, Restrictions
from portalab.core.errors import BadRequest, Conflict, Forbidden

PIN = re.compile(r"\d{4,6}")
COLOR = re.compile(r"#[0-9a-fA-F]{6}")
COLORS = ("#6366f1", "#ec4899", "#f59e0b", "#10b981", "#06b6d4", "#8b5cf6", "#ef4444", "#84cc16")
PROFILE_KINDS = ("standard", "child", "custom")
MAX_PROFILES = 8
ADULT = 18


class KeptTitle(BaseModel):
    """A title its master kept from a profile one by one (its name kept to list it)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    title: str = Field(default="", max_length=300)


class RestrictionSettings(BaseModel):
    """A profile's restrictions as stored and edited by its master: a fixed maximum age, or a birth date
    (the age then follows the profile, one more at each birthday); hidden or locked titles; access requests
    allowed or not."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_age: int | None = None
    birth_date: date | None = None
    allow_unrated: bool = True
    blocked: list[str] = Field(default_factory=list, max_length=len(FEATURES))
    mode: Mode = "hide"
    requests: bool = True
    genres: list[str] = Field(default_factory=list, max_length=len(GENRES))
    types: list[str] = Field(default_factory=list, max_length=len(TYPES))
    titles: list[KeptTitle] = Field(default_factory=list, max_length=500)
    daily_minutes: int | None = None
    services: bool = True  # « Open in Plex, Grimmory, RomM… » offered, or the portal's player and reader only

    @field_validator("types")
    @classmethod
    def _types(cls, value: list[str]) -> list[str]:
        unknown = [kind for kind in value if kind not in TYPES]
        if unknown:
            raise ValueError(f"unknown types {unknown}")
        return sorted(set(value))

    @field_validator("titles")
    @classmethod
    def _titles(cls, value: list[KeptTitle]) -> list[KeptTitle]:
        return list({title.id: title for title in value}.values())

    @field_validator("daily_minutes")
    @classmethod
    def _minutes(cls, value: int | None) -> int | None:
        if value is not None and value not in SCREEN_MINUTES:
            raise ValueError(f"daily_minutes must be one of {SCREEN_MINUTES}")
        return value

    @field_validator("genres")
    @classmethod
    def _genres(cls, value: list[str]) -> list[str]:
        unknown = [genre for genre in value if genre not in GENRES]
        if unknown:
            raise ValueError(f"unknown genres {unknown}")
        return sorted(set(value))

    @field_validator("birth_date")
    @classmethod
    def _born(cls, value: date | None) -> date | None:
        if value is not None and not date(1900, 1, 1) <= value <= datetime.now(UTC).date():
            raise ValueError("a birth date in the past")
        return value

    @field_validator("max_age")
    @classmethod
    def _age(cls, value: int | None) -> int | None:
        if value is not None and value not in AGES:
            raise ValueError(f"max_age must be one of {AGES}")
        return value

    @field_validator("blocked")
    @classmethod
    def _features(cls, value: list[str]) -> list[str]:
        unknown = [feature for feature in value if feature not in FEATURES]
        if unknown:
            raise ValueError(f"unknown features {unknown}")
        return sorted(set(value))

    def age(self, today: date) -> int | None:
        """Its age today, from its birth date."""
        if self.birth_date is None:
            return None
        born = self.birth_date
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

    def effective_age(self, today: date) -> int | None:
        """The age its titles are held to: its own until 18 (then no limit), else the fixed one."""
        age = self.age(today)
        if age is None:
            return self.max_age
        return None if age >= ADULT else age

    def restrictions(self, today: date | None = None) -> Restrictions:
        return Restrictions(
            self.effective_age(today or datetime.now(UTC).date()),
            self.allow_unrated,
            frozenset(self.blocked),
            self.mode,
            self.requests,
            frozenset(self.genres),
            frozenset(self.types),
            frozenset(str(title.id) for title in self.titles),
            self.daily_minutes,
            self.services,
        )


OPEN = RestrictionSettings()
CHILD = RestrictionSettings(
    max_age=12,
    allow_unrated=False,
    blocked=["ai", "community", "requests", "shop"],
    genres=["horror"],
    services=False,  # the portal's player and reader only: its screen time counts, its rules hold
)


def preset(kind: str) -> tuple[RestrictionSettings, bool]:
    """A kind's starting restrictions and community visibility: a child is restricted and kept out of the
    community; a standard (and, until its master chooses, a custom) profile is open and shown."""
    return (CHILD, False) if kind == "child" else (OPEN, True)


def parse(raw: Any) -> RestrictionSettings:
    try:
        return RestrictionSettings.model_validate(raw or {})
    except ValidationError:
        return CHILD  # a damaged record restricts rather than opens


def check_pin(pin: str) -> str:
    if not PIN.fullmatch(pin):
        raise InvalidPin("A PIN is 4 to 6 digits.")
    return pin


def color_for(raw: str | None, position: int) -> str:
    if raw is None:
        return COLORS[position % len(COLORS)]
    if not COLOR.fullmatch(raw):
        raise BadRequest("Choose a colour like #6366f1.", code="household.invalid_color")
    return raw.lower()


class InvalidPin(BadRequest):
    default_code = "household.invalid_pin"
    default_title = "Invalid PIN"


class OwnerOnly(Forbidden):
    default_code = "household.owner_only"
    default_title = "Only the account's master can do this"


class ProfileLimit(Conflict):
    default_code = "household.limit"
    default_title = "No more profiles"
