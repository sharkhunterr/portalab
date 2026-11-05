"""Members directory (T007; US1): active accounts from ``identity.members``, each shown only if the member's
``member_listing`` visibility allows this viewer (021, listing surface). Ordering is by display name or
join date only — never by a hidden attribute. Pages are filled in bounded batches so a filtered page is
never silently short while more visible members remain. Issue 347: a member who keeps their progression to
themselves (anonymous) is still a member of the community — the directory counts them at its end, without
name, avatar, join date nor profile, never in a search (where they stood would tell who they are)."""

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
PROGRESSION = "progression"  # owned by gamification (013): « public » or « anonymous » in the community


@dataclass(frozen=True, slots=True)
class Member:
    id: UUID
    display_name: str
    joined_at: datetime


@dataclass(frozen=True, slots=True)
class MembersPage:
    items: list[Member]
    next_offset: int | None
    anonymous: int = 0  # issue 347: on the last page, the anonymous members counted at the end


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

    async def named(self, viewer: Principal, member: UUID) -> bool:
        """Issue 347: whether the viewer may know who this member is (not anonymous; one knows themself)."""
        return member == (viewer.acting_for or viewer.user_id) or await shown(
            self.visibility, viewer, member, PROGRESSION, True
        )

    async def anonymous(self, viewer: Principal) -> int:
        """Issue 347: how many listed members are anonymous to this viewer."""
        listing = self._listing()
        count = 0
        cursor: int | None = 0
        while cursor is not None:
            batch = await listing.active_members(offset=cursor, limit=100)
            for entry in batch.items:
                if await self.listed(viewer, entry.id) and not await self.named(viewer, entry.id):
                    count += 1
            cursor = batch.next_offset
        return count

    async def page(
        self,
        viewer: Principal,
        *,
        query: str | None = None,
        offset: int = 0,
        limit: int = 30,
        newest: bool = False,
        anonymous: bool = True,
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
                if await self.listed(viewer, entry.id) and await self.named(viewer, entry.id):
                    items.append(Member(entry.id, entry.display_name, entry.joined_at))
                    if len(items) == limit:
                        break
            if len(items) == limit:
                more = consumed < len(batch.items) or batch.next_offset is not None
                return MembersPage(items, cursor + consumed if more else None)
            cursor = batch.next_offset
        counted = await self.anonymous(viewer) if cursor is None and anonymous and not query else 0
        return MembersPage(items, cursor, counted)

    async def get(self, viewer: Principal, member: UUID) -> tuple[str, bool] | None:
        """``(display_name, listed)`` for an active member, ``None`` otherwise (unknown or not active, or
        anonymous to this viewer — issue 347: an anonymous member has no profile for the others)."""
        directory = self.directory()
        if directory is None:
            raise Unavailable("The members directory is not available.", code="community.unavailable")
        summary = await directory.get_user_summary(member)
        if summary is None or not summary.is_active or summary.anonymized or not summary.display_name:
            return None
        if not await self.named(viewer, member):
            return None
        return summary.display_name, await self.listed(viewer, member)
