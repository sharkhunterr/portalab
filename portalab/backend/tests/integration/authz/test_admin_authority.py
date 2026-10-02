"""003 T024 — single-Admin authority: first grant only when none; second Admin refused; delegation and
assignment of the Admin role refused and audited; sole-Admin revoke refused; concurrent transfers ⇒ one."""

import asyncio

import pytest
from sqlalchemy import func, select

from portalab.capabilities.admin_authority import AdminAlreadyExists, AdminTransferRefused
from portalab.core.event_port import OutboxEvent
from portalab.modules.authz.grants.service import SoleAdminProtected
from portalab.modules.authz.models import ADMIN_ROLE_ID, AuditEntry, UserRole
from tests.authz_fixtures import AuthzPlatform, insert_user, make_admin, user


async def _active_admins(platform: AuthzPlatform) -> list[object]:
    async with platform.database.session() as session:
        return list(
            (
                await session.execute(
                    select(UserRole.user_id).where(
                        UserRole.role_id == ADMIN_ROLE_ID, UserRole.revoked_at.is_(None)
                    )
                )
            ).scalars()
        )


async def test_first_grant_then_second_admin_refused(platform: AuthzPlatform) -> None:
    first, second = await insert_user(platform.database), await insert_user(platform.database)
    await make_admin(platform, first)
    with pytest.raises(AdminAlreadyExists):
        await make_admin(platform, second)
    assert await _active_admins(platform) == [first]
    async with platform.database.session() as session:
        assert await platform.authz.admin_authority.is_admin(session, first)
        assert await platform.authz.admin_authority.current_admin(session) == first
    assert await platform.authz.engine.is_allowed(user(first), "users.admin.transfer")
    assert not await platform.authz.engine.is_allowed(user(second), "users.admin.transfer")


async def test_admin_role_is_never_assigned_delegated_or_revoked(platform: AuthzPlatform) -> None:
    admin, other = await insert_user(platform.database), await insert_user(platform.database)
    await make_admin(platform, admin)
    with pytest.raises(SoleAdminProtected):
        await platform.authz.grants.assign_role(user(admin), other, "admin")
    with pytest.raises(SoleAdminProtected):
        await platform.authz.grants.revoke_role(user(admin), admin, "admin")
    assert await _active_admins(platform) == [admin]
    async with platform.database.session() as session:
        refused = await session.scalar(
            select(func.count()).select_from(AuditEntry).where(AuditEntry.action == "admin.transfer_refused")
        )
        events = list((await session.execute(select(OutboxEvent.type))).scalars())
    assert refused == 2
    assert events.count("permission.admin_transfer_attempted") >= 3  # first grant + two refusals


async def test_concurrent_transfers_have_exactly_one_winner(platform: AuthzPlatform) -> None:
    admin = await insert_user(platform.database)
    await make_admin(platform, admin)
    heirs = [await insert_user(platform.database) for _ in range(4)]

    async def transfer(heir: object) -> None:
        async with platform.database.unit_of_work() as uow:
            await platform.authz.admin_authority.transfer_admin(uow.session, admin, heir, user(admin))  # type: ignore[arg-type]

    results = await asyncio.gather(*(transfer(heir) for heir in heirs), return_exceptions=True)
    assert sum(result is None for result in results) == 1
    assert all(isinstance(r, AdminTransferRefused) for r in results if r is not None)
    admins = await _active_admins(platform)
    assert len(admins) == 1 and admins[0] in heirs
    assert not await platform.authz.engine.is_allowed(user(admin), "users.roles.manage")


async def test_transfer_to_self_is_refused(platform: AuthzPlatform) -> None:
    admin = await insert_user(platform.database)
    await make_admin(platform, admin)
    with pytest.raises(AdminTransferRefused):
        async with platform.database.unit_of_work() as uow:
            await platform.authz.admin_authority.transfer_admin(uow.session, admin, admin, user(admin))
    assert await _active_admins(platform) == [admin]
