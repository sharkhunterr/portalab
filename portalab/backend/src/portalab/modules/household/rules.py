"""Household rules (spec 032): the kinds' presets, the restrictions as stored, PINs and colours."""

import re
from datetime import UTC, date, datetime
from itertools import pairwise
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from portalab.capabilities.household import (
    AGES,
    FEATURES,
    SCREEN_MINUTES,
    TYPES,
    Mode,
    Restrictions,
    Slot,
    genre_key,
)
from portalab.core.errors import BadRequest, Conflict, Forbidden

PIN = re.compile(r"\d{4,6}")
HOUR = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d")
END = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d|24:00")
MAX_SLOTS = 42  # six spans a day
MAX_GENRES = 40
DAY_MINUTES = 24 * 60
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


class SlotIn(BaseModel):
    """Issue 432: a span of a weekday a profile may watch, with its own screen time (none: the whole span)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    day: int = Field(ge=0, le=6)  # Monday first
    start: str
    end: str
    minutes: int | None = Field(default=None, ge=5, le=DAY_MINUTES)

    @model_validator(mode="after")
    def _span(self) -> "SlotIn":
        if not HOUR.fullmatch(self.start) or not END.fullmatch(self.end) or self.end <= self.start:
            raise ValueError("a span from HH:MM to a later HH:MM (24:00 at most)")
        return self


# issue 478: the countries whose age ratings a profile may also be held to (those the portal keeps)
RatingCountry = Literal["FR", "DE", "GB", "US", "ES", "IT", "BE", "CH", "NL", "CA", "AU"]
# issue 478: the warnings a master may keep a profile from — the CNC's « tous publics avec avertissement »
# and the rating boards' descriptors, by family
WarningKind = Literal[
    "cnc", "violence", "fear", "language", "drugs", "sex", "self_harm", "discrimination", "mature"
]


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
    genres: list[str] = Field(default_factory=list, max_length=MAX_GENRES)  # issue 432: any genre
    types: list[str] = Field(default_factory=list, max_length=len(TYPES))
    titles: list[KeptTitle] = Field(default_factory=list, max_length=500)
    daily_minutes: int | None = None
    services: bool = True  # « Open in Plex, Grimmory, RomM… » offered, or the portal's player and reader only
    # issue 432: a weekly plan (Monday first; ``None`` a day without limit, 0 a day without screen) and the
    # hours it may watch (« HH:MM », both or none; an overnight span too)
    week_minutes: list[int | None] | None = None
    hours_from: str | None = None
    hours_to: str | None = None
    slots: list[SlotIn] = Field(default_factory=list, max_length=MAX_SLOTS)
    # issue 439: its screen time counts its media only, or all of its time on the portal
    screen_scope: Literal["media", "portal"] = "media"
    # issue 478: other countries whose age ratings count too (the strictest wins) — ``None``: as the portal's
    # administrator set it (none by default), a list: its master's own choice (empty: the portal's country)
    rating_countries: list[RatingCountry] | None = None
    # issue 478: titles carrying one of these warnings are kept from it; its age read as the strictest of
    # its countries' ratings, or the average of every country's
    avoid_warnings: list[WarningKind] = Field(default_factory=list, max_length=9)
    rating_blend: Literal["strictest", "average"] = "strictest"

    @field_validator("slots")
    @classmethod
    def _slots(cls, value: list[SlotIn]) -> list[SlotIn]:
        """Spans of one day never overlap; kept in order."""
        ordered = sorted(value, key=lambda s: (s.day, s.start))
        for before, after in pairwise(ordered):
            if before.day == after.day and after.start < before.end:
                raise ValueError("two spans of a day overlap")
        return ordered

    @field_validator("week_minutes")
    @classmethod
    def _week(cls, value: list[int | None] | None) -> list[int | None] | None:
        if value is None:
            return None
        if len(value) != 7 or any(m is not None and not 0 <= m <= DAY_MINUTES for m in value):
            raise ValueError("week_minutes: seven days, each from 0 to 1440 minutes or none")
        return value

    @field_validator("hours_from", "hours_to")
    @classmethod
    def _hour(cls, value: str | None) -> str | None:
        if value is not None and not HOUR.fullmatch(value):
            raise ValueError("an hour as HH:MM")
        return value

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
        """Issue 432: any genre of the catalog — kept as its key (the four known ones, whatever their
        language), else its words lowercased."""
        keys = {genre_key(genre) for genre in value if genre.strip()}
        return sorted(key for key in keys if key)

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

    def restrictions(
        self, today: date | None = None, *, bonus_minutes: int = 0, bonus_day: date | None = None
    ) -> Restrictions:
        hours = (self.hours_from, self.hours_to) if self.hours_from and self.hours_to else None
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
            tuple(self.week_minutes) if self.week_minutes is not None else None,
            hours,
            bonus_minutes,
            bonus_day,
            tuple(Slot(s.day, s.start, s.end, s.minutes) for s in self.slots),
            self.screen_scope,
            tuple(self.rating_countries) if self.rating_countries is not None else None,
            frozenset(self.avoid_warnings),
            self.rating_blend,
        )


OPEN = RestrictionSettings()
CHILD = RestrictionSettings(
    max_age=12,
    allow_unrated=False,
    blocked=["ai", "community", "requests", "shop"],
    genres=["horror", "thriller", "crime", "war"],  # issue 432: at least these, whatever their rating
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
