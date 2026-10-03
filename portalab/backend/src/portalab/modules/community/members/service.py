"""Members directory (T007; US1): active accounts from ``identity.members``, each shown only if the member's
``member_listing`` visibility allows this viewer (021, listing surface). Ordering is by display name or
join date only — never by a hidden attribute. Pages are filled in bounded batches so a filtered page is
never silently short while more visible members remain."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from portalab.capabilities.identity_directory import (
    CAPABILITY as DIRECTORY,
)
from portalab.capabilities.identity_directory import (
    MEMBERS,
    IdentityDirectory,
    MemberListing,
)
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.errors import Unavailable
from portalab.core.visibility_port import VisibilityFilter
from portalab.modules.community.preferences import MEMBER_LISTING, shown

MAX_BATCHES = 8


@dataclass(frozen=True, slots=True)
class Member:
    id: UUID
    display_name: str
    joined_at: datetime


@dataclass(frozen=True, slots=True)
class MembersPage:
    items: list[Member]
    next_offset: int | None


class Members:
    def __init__(self, capabilities: CapabilityRegistry, visibility: VisibilityFilter) -> None:
        self.capabilities = capabilities
        self.visibility = visibility

    def _listing(self) -> MemberListing:
        providers = self.capabilities.system_providers(MEMBERS)
        if not providers:
            raise Unavailable("The members directory is not available.", code="community.unavailable")
        return providers[0].provider  # type: ignore[no-any-return]

    def directory(self) -> IdentityDirectory | None:
        providers = self.capabilities.system_providers(DIRECTORY)
        return providers[0].provider if providers else None

    async def listed(self, viewer: Principal, member: UUID) -> bool:
        return await shown(self.visibility, viewer, member, MEMBER_LISTING, True, surface="listing")

    async def page(
        self,
        viewer: Principal,
        *,
        query: str | None = None,
        offset: int = 0,
        limit: int = 30,
        newest: bool = False,
    ) -> MembersPage:
        limit = max(1, min(limit, 100))
        listing = self._listing()
        items: list[Member] = []
        cursor: int | None = max(0, offset)
        for _ in range(MAX_BATCHES):
            if cursor is None:
                break
            batch = await listing.active_members(query=query, offset=cursor, limit=limit, newest=newest)
            consumed = 0
            for entry in batch.items:
                consumed += 1
                if await self.listed(viewer, entry.id):
                    items.append(Member(entry.id, entry.display_name, entry.joined_at))
                    if len(items) == limit:
                        break
            if len(items) == limit:
                more = consumed < len(batch.items) or batch.next_offset is not None
                return MembersPage(items, cursor + consumed if more else None)
            cursor = batch.next_offset
        return MembersPage(items, cursor)

    async def get(self, viewer: Principal, member: UUID) -> tuple[str, bool] | None:
        """``(display_name, listed)`` for an active member, ``None`` otherwise (unknown or not active)."""
        directory = self.directory()
        if directory is None:
            raise Unavailable("The members directory is not available.", code="community.unavailable")
        summary = await directory.get_user_summary(member)
        if summary is None or not summary.is_active or summary.anonymized or not summary.display_name:
            return None
        return summary.display_name, await self.listed(viewer, member)
