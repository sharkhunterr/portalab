"""Household rules (spec 032): the kinds' presets, the restrictions as stored, PINs and colours."""

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from portalab.capabilities.household import AGES, FEATURES, Restrictions
from portalab.core.errors import BadRequest, Conflict, Forbidden

PIN = re.compile(r"\d{4,6}")
COLOR = re.compile(r"#[0-9a-fA-F]{6}")
COLORS = ("#6366f1", "#ec4899", "#f59e0b", "#10b981", "#06b6d4", "#8b5cf6", "#ef4444", "#84cc16")
PROFILE_KINDS = ("standard", "child", "custom")
MAX_PROFILES = 8


class RestrictionSettings(BaseModel):
    """A profile's restrictions as stored and edited by its master."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_age: int | None = None
    allow_unrated: bool = True
    blocked: list[str] = Field(default_factory=list, max_length=len(FEATURES))

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

    def restrictions(self) -> Restrictions:
        return Restrictions(self.max_age, self.allow_unrated, frozenset(self.blocked))


OPEN = RestrictionSettings()
CHILD = RestrictionSettings(max_age=12, allow_unrated=False, blocked=["ai", "community", "requests", "shop"])


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


class WrongPin(Forbidden):
    default_code = "household.wrong_pin"
    default_title = "Wrong PIN"


class OwnerOnly(Forbidden):
    default_code = "household.owner_only"
    default_title = "Only the account's master can do this"


class HouseholdDisabled(Forbidden):
    default_code = "household.disabled"
    default_title = "Profiles are switched off"


class ProfileLimit(Conflict):
    default_code = "household.limit"
    default_title = "No more profiles"
