"""Effective grants of a user (T013): implicit ``user`` role + active roles + active groups + entitlement
grants held by the user. Read from the database on every request (memoized for the request only, R6), so
assignments and revocations take effect on the very next evaluation."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.modules.authz.models import ADMIN_ROLE_ID, BASE_ROLE_IDS, Grant, UserGroup, UserRole


@dataclass(frozen=True, slots=True)
class GrantRow:
    permission_key: str
    effect: str
    scope_kind: str
    scope_ref: str


@dataclass(frozen=True, slots=True)
class EffectiveGrants:
    user_id: UUID
    is_admin: bool
    role_ids: frozenset[UUID]
    group_ids: frozenset[UUID]
    grants: tuple[GrantRow, ...]

    def for_permission(self, key: str) -> list[GrantRow]:
        return [grant for grant in self.grants if grant.permission_key == key]


async def load_effective_grants(session: AsyncSession, user_id: UUID) -> EffectiveGrants:
    role_ids = set(
        (
            await session.execute(
                select(UserRole.role_id).where(UserRole.user_id == user_id, UserRole.revoked_at.is_(None))
            )
        ).scalars()
    )
    role_ids.add(BASE_ROLE_IDS["user"])  # every account holds the base User role (FR-006)
    group_ids = set(
        (
            await session.execute(
                select(UserGroup.group_id).where(UserGroup.user_id == user_id, UserGroup.revoked_at.is_(None))
            )
        ).scalars()
    )
    holders = [(Grant.holder_kind == "role") & Grant.holder_id.in_(role_ids)]
    if group_ids:
        holders.append((Grant.holder_kind == "group") & Grant.holder_id.in_(group_ids))
    holders.append((Grant.holder_kind == "user") & (Grant.holder_id == user_id))
    rows = (
        await session.execute(
            select(Grant.permission_key, Grant.effect, Grant.scope_kind, Grant.scope_ref)
            .where(or_(*holders))
            .order_by(Grant.permission_key, Grant.effect, Grant.scope_kind, Grant.scope_ref)
        )
    ).all()
    return EffectiveGrants(
        user_id=user_id,
        is_admin=ADMIN_ROLE_ID in role_ids,
        role_ids=frozenset(role_ids),
        group_ids=frozenset(group_ids),
        grants=tuple(GrantRow(*row) for row in rows),
    )
