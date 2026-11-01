"""Quest definitions (T039; R11, OQ-62 default): closed and versioned.

* ``quest`` — steps over event counts, once (``period: none``) or each week (``period: week``);
* ``daily`` — a daily objective (``period: day``; ``week`` for weekly objectives), reset each period;
* ``challenge`` — a **time-boxed quest**: a ``window`` is required and only events inside it count;
* ``discovery`` (027) — a new member's first steps (fill the profile, take the tour…): once, no window.
Steps reuse the achievements' ``event_count`` criterion; rewards go through the ledger. ``complete_on``:
``all`` steps (the default) or ``any`` one of them (issue 121: a first step is done by its guided tour or by
doing the thing). #307: ``translations`` gives the label and description in other interface languages
(``{"fr": {"label": …, "description": …}}``); a member reads the one of their language, else ``label``."""

from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, model_validator

from portalab.core.errors import ValidationFailed
from portalab.modules.gamification.achievements.definition import EventCount, Reward, Unlock

QuestKind = Literal["quest", "daily", "challenge", "discovery"]
Period = Literal["none", "day", "week", "month"]


class Window(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def _ordered(self) -> "Window":
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise ValueError("window instants carry a time zone offset")
        if self.ends_at <= self.starts_at:
            raise ValueError("a window ends after it starts")
        return self


class SettingIn(BaseModel):
    """027: a quest that counts only for members who **chose** one of these values themselves — the
    interface they wear (``ui.theme``: « christmas »…) or their palette (``ui.palette``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["setting_in"] = "setting_in"
    setting: Literal["ui.theme", "ui.palette"]
    values: list[str] = Field(min_length=1, max_length=50)


class QuestText(BaseModel):
    """#307: a quest's texts in another language."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    label: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=400)


Language = Annotated[str, Field(pattern=r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")]


class QuestDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: QuestKind
    label: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=400)
    icon: str | None = Field(default=None, max_length=64)
    period: Period = "none"
    window: Window | None = None
    steps: list[EventCount] = Field(min_length=1, max_length=5)
    complete_on: Literal["all", "any"] = "all"
    rewards: list[Reward] = Field(default_factory=list, max_length=3)
    # 027: shop products the quest gives (a sealed booster to open from the reserve, a badge…)
    unlocks: list[Unlock] = Field(default_factory=list, max_length=3)
    # 027: who it counts for (all must hold when the event comes): e.g. members wearing a Christmas interface
    requires: list[SettingIn] = Field(default_factory=list, max_length=3)
    translations: dict[Language, QuestText] = Field(default_factory=dict, max_length=10)  # #307

    @model_validator(mode="after")
    def _coherent(self) -> "QuestDefinition":
        if self.kind == "daily" and self.period == "none":
            raise ValueError("a daily objective resets each day, week or month")
        if self.kind == "challenge" and (self.window is None or self.period != "none"):
            raise ValueError("a challenge is a time-boxed quest: a window and no period")
        if self.kind == "discovery" and (self.period != "none" or self.window is not None):
            raise ValueError("a discovery mission is done once: no period and no window")
        if self.kind == "quest" and self.period == "day":
            raise ValueError("a quest repeating each day is a daily objective")
        return self

    def open_at(self, at: datetime) -> bool:
        return self.window is None or self.window.starts_at <= at < self.window.ends_at


_ADAPTER = TypeAdapter(QuestDefinition)


def parse_quest(raw: Mapping[str, Any]) -> QuestDefinition:
    try:
        return _ADAPTER.validate_python(dict(raw))
    except ValidationError as exc:
        raise ValidationFailed(
            "This quest is not valid.",
            code="economy.quest_invalid",
            extensions={"errors": [e["msg"][:200] for e in exc.errors()][:10]},
        ) from exc
