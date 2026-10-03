"""Funding rules (R4, OQ-71 default) — set by the Admin when a project opens and **immutable afterwards**:
refund percentages on reject/abandon (100 % by default), consumption at release or by milestones (each a
state on the forward path and a percentage, summing to 100), per-funding bounds and a display-only goal."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from portalab.core.errors import ValidationFailed

MILESTONE_STATES = ("validation", "development", "beta", "released")


class Milestone(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    state: Literal["validation", "development", "beta", "released"]
    percent: int = Field(ge=1, le=100)


class FundingRules(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    # Funders are refunded in full when a project fails (a partial refund would need the 013 ledger to
    # split a reservation; recorded as a deviation, see docs/marketplace.md).
    refund_on_reject: Literal[100] = 100
    refund_on_abandon: Literal[100] = 100
    consume_at: Literal["released"] | list[Milestone] = "released"
    min_funding: int = Field(default=1, ge=1, le=1_000_000)
    max_funding_per_user: int = Field(default=1000, ge=1, le=10_000_000)
    goal_amount: int | None = Field(default=None, ge=1, le=1_000_000_000)

    @model_validator(mode="after")
    def _coherent(self) -> "FundingRules":
        if isinstance(self.consume_at, list):
            states = [m.state for m in self.consume_at]
            if not states or len(set(states)) != len(states):
                raise ValueError("milestones name distinct states")
            if sum(m.percent for m in self.consume_at) != 100:
                raise ValueError("milestone percentages add up to 100")
            if states != sorted(states, key=MILESTONE_STATES.index):
                raise ValueError("milestones follow the lifecycle order")
        if self.max_funding_per_user < self.min_funding:
            raise ValueError("the per-member maximum is at least the minimum")
        return self

    def tranches(self) -> list[tuple[str, int]]:
        """``(consume_at state, percent)`` pairs."""
        if isinstance(self.consume_at, list):
            return [(m.state, m.percent) for m in self.consume_at]
        return [("released", 100)]


def parse_rules(raw: dict[str, Any]) -> FundingRules:
    try:
        return FundingRules.model_validate(raw)
    except ValidationError as exc:
        raise ValidationFailed(
            "These funding rules are not valid.",
            code="project.invalid_rules",
            extensions={"errors": [e["msg"][:200] for e in exc.errors()][:10]},
        ) from exc


def split(amount: int, rules: FundingRules) -> list[tuple[str, int]]:
    """Split a funding into tranches by percentage (remainder on the last), dropping empty ones."""
    parts = rules.tranches()
    out: list[tuple[str, int]] = []
    left = amount
    for index, (state, percent) in enumerate(parts):
        share = left if index == len(parts) - 1 else amount * percent // 100
        left -= share
        if share > 0:
            out.append((state, share))
    return out
