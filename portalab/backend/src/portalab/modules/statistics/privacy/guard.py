"""``PrivacyGuard`` (T012; R5): personal statistics are owner-only unless the owner's visibility for the
datum class ``statistics`` allows the viewer (021); community values need ``min_cohort_size`` distinct
contributors, and small dimension cells are merged into "other" — with extra cells suppressed when needed
so totals minus visible cells never reveal a small group."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from portalab.capabilities.visibility import register_datum_class
from portalab.core.authz_port import Principal
from portalab.core.visibility_port import OwnerOnlyVisibility, Redacted, VisibilityFilter

DATUM_CLASS = "statistics"
OTHER = {"__other__": "other"}

register_datum_class(
    DATUM_CLASS,
    owner="module:statistics",
    default_level="private",
    classification="activity",
    description="Personal statistics (activity summaries)",
    user_choosable=False,
)


@dataclass
class Cell:
    dims: dict[str, str]
    value: float
    contributors: int


class PrivacyGuard:
    def __init__(self, visibility: VisibilityFilter | None = None) -> None:
        self.visibility: VisibilityFilter = visibility or OwnerOnlyVisibility()

    async def subject_visible(self, viewer: Principal, subject: UUID, stat_key: str) -> bool:
        owner = viewer.acting_for or viewer.user_id
        if owner == subject:
            return True
        shown = await self.visibility.filter(viewer, subject, DATUM_CLASS, stat_key, True)
        return not isinstance(shown, Redacted)

    @staticmethod
    def suppress(cells: Sequence[Cell], threshold: int, merge: Any = None) -> list[dict[str, Any]]:
        """Visible cells (≥ threshold) plus an "other" cell when it is itself ≥ threshold. ``merge`` sums
        two values (default addition; min/max/distinct pass their own)."""
        combine = merge or (lambda a, b: a + b)
        visible = sorted(
            (c for c in cells if c.contributors >= threshold), key=lambda c: (-c.value, str(c.dims))
        )
        hidden = [c for c in cells if c.contributors < threshold]
        while hidden and sum(c.contributors for c in hidden) < threshold and visible:
            hidden.append(visible.pop())  # the smallest visible cell joins "other" so it cannot be inferred
        out = [{"dims": c.dims, "value": c.value} for c in visible]
        if hidden and sum(c.contributors for c in hidden) >= threshold:
            value = hidden[0].value
            for cell in hidden[1:]:
                value = combine(value, cell.value)
            out.append({"dims": OTHER, "value": value})
        return out
