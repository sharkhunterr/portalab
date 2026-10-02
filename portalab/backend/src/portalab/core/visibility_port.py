"""``VisibilityFilter`` port (spec 003 T032; implemented by Privacy, spec 021).

Ordering rule, portal-wide: **authorize, then filter**. ``require()`` decides whether the viewer may perform
the action at all (permissions, spec 003); the ``VisibilityFilter`` then redacts each personal datum according
to the owner's visibility preference and the admin policies (FR-031..033). The authorization engine never
reads nor changes visibility, and a read permission never overrides a Private preference.

Until Privacy is installed, :class:`OwnerOnlyVisibility` is the safe default: personal data is visible to its
owner only (CD-016 "historized ≠ public; default not-public/owner-only").
"""

from dataclasses import dataclass
from typing import Any, Literal, Protocol
from uuid import UUID

from portalab.core.authz_port import Principal

Level = Literal["public", "community", "leaderboard", "private"]


@dataclass(frozen=True, slots=True)
class Redacted:
    datum_class: str


class VisibilityFilter(Protocol):
    async def filter(
        self, viewer: Principal, subject: UUID, datum_class: str, datum_ref: str | None, value: Any
    ) -> Any | Redacted: ...

    async def effective_level(self, subject: UUID, datum_class: str, datum_ref: str | None) -> Level: ...


class OwnerOnlyVisibility:
    """Default before spec 021: everything personal is private to its owner."""

    async def filter(
        self, viewer: Principal, subject: UUID, datum_class: str, datum_ref: str | None, value: Any
    ) -> Any | Redacted:
        owner = viewer.acting_for or viewer.user_id
        return value if owner == subject else Redacted(datum_class)

    async def effective_level(self, subject: UUID, datum_class: str, datum_ref: str | None) -> Level:
        return "private"
