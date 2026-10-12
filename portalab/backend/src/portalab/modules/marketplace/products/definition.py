"""Product versions (T020; R7, R8, R12, FR-019/020): a closed definition — price in Coins (none: free),
conditions from a closed set combined with **AND** (``min_level``, ``min_contribution`` — 027: the
community points a member has earned, to keep some products for those who take part —, ``achievement``,
``campaign_active``, ``role``), a refund policy, localized names and descriptions, whether the owner
must configure it, and a type-specific ``payload`` limited to the keys the product type declares. Nothing
may express a priority: any priority-like key is rejected (no paid priority anywhere, OQ-72)."""

import re
from collections.abc import Mapping
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from portalab.core.errors import ValidationFailed

PRIORITY_LIKE = re.compile(r"(priorit|queue|boost|skip|fast.?track|jump|ahead|rank|order)", re.IGNORECASE)
LANG = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})?$")


class MinLevel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["min_level"]
    level: int = Field(ge=1, le=1000)


class MinContribution(BaseModel):
    """027: at least this much Contribution (points earned by helping the community)."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["min_contribution"]
    contribution: int = Field(ge=1, le=1_000_000)


class AchievementCondition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["achievement"]
    achievement: str = Field(min_length=1, max_length=96)


class CampaignActive(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["campaign_active"]
    campaign: str = Field(min_length=1, max_length=96)


class RoleCondition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["role"]
    role: str = Field(min_length=1, max_length=64)


Condition = Annotated[
    MinLevel | MinContribution | AchievementCondition | CampaignActive | RoleCondition,
    Field(discriminator="kind"),
]


class RefundPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    refundable: bool = True
    window_days: int = Field(default=7, ge=0, le=365)
    percent: int = Field(default=100, ge=0, le=100)


class ProductVersionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    price_coins: int | None = Field(default=None, ge=1, le=1_000_000)
    conditions: list[Condition] = Field(default_factory=list, max_length=8)
    refund_policy: RefundPolicy | None = None
    names: dict[str, str] = Field(min_length=1, max_length=12)
    descriptions: dict[str, str] = Field(default_factory=dict, max_length=12)
    payload: dict[str, Any] = Field(default_factory=dict)
    config_required: bool = False

    @field_validator("names", "descriptions")
    @classmethod
    def _languages(cls, value: dict[str, str]) -> dict[str, str]:
        for lang, text in value.items():
            if not LANG.fullmatch(lang) or not text.strip() or len(text) > 4000:
                raise ValueError("texts are keyed by language and not empty")
        return value


Rarity = Literal["common", "rare", "epic", "legendary"]
PosterEffect = Literal["auto", "none", "shine", "glitch", "spin", "neon", "blink"]


class PresentationIn(BaseModel):
    """Shop presentation (027 US8): changes it without a new price version."""

    model_config = ConfigDict(extra="forbid")
    rarity: Rarity = "common"
    featured: bool = False
    poster_effect: PosterEffect = "auto"
    icon: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9-]{0,63}$")
    # #81: the season it belongs to (Halloween, Christmas…) — its season's booster and pack draw from it
    season: Literal["valentine", "spring", "summer", "halloween", "christmas"] | None = None


class AvailabilityIn(BaseModel):
    """027: scarcity — copies (``None``: the rarity's supply) and a purchase limit per period."""

    model_config = ConfigDict(extra="forbid")
    supply: int | None = Field(default=None, ge=1, le=1_000_000)
    limit_count: int | None = Field(default=None, ge=1, le=1000)
    limit_days: int | None = Field(default=None, ge=1, le=366)

    @field_validator("limit_days")
    @classmethod
    def _both(cls, value: int | None, info: Any) -> int | None:
        if (value is None) != (info.data.get("limit_count") is None):
            raise ValueError("a purchase limit needs both a count and a period")
        return value


class ProductIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(pattern=r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$", max_length=96)
    type: str = Field(min_length=1, max_length=96)
    category: str | None = Field(default=None, max_length=64)
    repeatable: bool = False
    presentation: PresentationIn = Field(default_factory=PresentationIn)
    availability: AvailabilityIn = Field(default_factory=AvailabilityIn)
    version: ProductVersionIn


def _keys(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        return [str(k) for k in value] + [k for v in value.values() for k in _keys(v)]
    if isinstance(value, list):
        return [k for v in value for k in _keys(v)]
    return []


def check_payload(payload: Mapping[str, Any], allowed: tuple[str, ...]) -> None:
    priority = [k for k in _keys(payload) if PRIORITY_LIKE.search(k)]
    if priority:
        raise ValidationFailed(
            "Products cannot buy any priority.",
            code="marketplace.priority_forbidden",
            extensions={"keys": priority},
        )
    unknown = sorted(set(payload) - set(allowed))
    if unknown:
        raise ValidationFailed(
            "This product type does not take these settings.",
            code="marketplace.invalid_product",
            extensions={"keys": unknown},
        )


def parse_product(raw: Mapping[str, Any]) -> ProductIn:
    try:
        return ProductIn.model_validate(dict(raw))
    except ValidationError as exc:
        priority = [k for k in _keys(raw) if PRIORITY_LIKE.search(k)]
        if priority:
            raise ValidationFailed(
                "Products cannot buy any priority.",
                code="marketplace.priority_forbidden",
                extensions={"keys": priority},
            ) from exc
        raise ValidationFailed(
            "This product is not valid.",
            code="marketplace.invalid_product",
            extensions={"errors": [e["msg"][:200] for e in exc.errors()][:10]},
        ) from exc


def parse_version(raw: Mapping[str, Any]) -> ProductVersionIn:
    try:
        return ProductVersionIn.model_validate(dict(raw))
    except ValidationError as exc:
        priority = [k for k in _keys(raw) if PRIORITY_LIKE.search(k)]
        if priority:
            raise ValidationFailed(
                "Products cannot buy any priority.",
                code="marketplace.priority_forbidden",
                extensions={"keys": priority},
            ) from exc
        raise ValidationFailed(
            "This product is not valid.",
            code="marketplace.invalid_product",
            extensions={"errors": [e["msg"][:200] for e in exc.errors()][:10]},
        ) from exc
