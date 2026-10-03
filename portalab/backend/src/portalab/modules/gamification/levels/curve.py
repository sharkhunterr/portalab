"""Level curve (T006/T008; R5): the Level is **derived** from total XP, never stored as a value. Default
(OQ-60): cumulative threshold ``round(base · (n - 1)^exponent)`` — level 1 at 0 XP, level 2 at 100,
level 3 at 283… Curves are versioned; a new version recomputes cached levels without emitting level-ups."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

MAX_LEVEL = 1000


class CurveDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: str = Field(default="power", pattern=r"^power$")
    base: int = Field(default=100, ge=1, le=1_000_000)
    exponent: float = Field(default=1.5, ge=1.0, le=3.0)


DEFAULT_CURVE: dict[str, Any] = CurveDefinition().model_dump()


@dataclass(frozen=True, slots=True)
class Curve:
    version: int
    base: int = 100
    exponent: float = 1.5

    @classmethod
    def of(cls, version: int, definition: Mapping[str, Any]) -> "Curve":
        parsed = CurveDefinition.model_validate(dict(definition))
        return cls(version, parsed.base, parsed.exponent)

    def threshold(self, level: int) -> int:
        """Total XP needed to reach ``level`` (monotonic)."""
        return 0 if level <= 1 else round(self.base * (level - 1) ** self.exponent)

    def level_for(self, xp: int) -> int:
        low, high = 1, MAX_LEVEL
        while low < high:
            middle = (low + high + 1) // 2
            if self.threshold(middle) <= xp:
                low = middle
            else:
                high = middle - 1
        return low

    def next_threshold(self, xp: int) -> int | None:
        level = self.level_for(xp)
        return None if level >= MAX_LEVEL else self.threshold(level + 1)
