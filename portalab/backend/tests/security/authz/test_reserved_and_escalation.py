"""003 T021 — reserved permissions cannot be granted to non-Admin roles, groups, plugins or users; no
aggregation of roles/groups reaches Admin-only authority; base roles are undeletable."""

import pytest
from sqlalchemy import select

from portalab.core.errors import ValidationFailed
from portalab.core.permissions import PermissionDeclarationError, PermissionRegistry
from portalab.modules.authz.grants.service import GrantSpec, ReservedPermission
from portalab.modules.authz.models import BASE_ROLE_IDS, Permission
from tests.authz_fixtures import AuthzPlatform, insert_user, user

pytestmark = pytest.mark.integration


async def _reserved(platform: AuthzPlatform) -> list[str]:
    async with platform.database.session() as session:
        return list((await session.execute(select(Permission.key).where(Permission.reserved))).scalars())


async def test_reserved_set_is_not_grantable(platform: AuthzPlatform) -> None:
    reserved = await _reserved(platform)
    assert {"users.admin.transfer", "users.roles.manage", "security.manage"} <= set(reserved)
    group = await platform.authz.grants.create_group(user(await insert_user(platform.database)), "ops", "Ops")
    member = await insert_user(platform.database)
    for key in reserved:
        with pytest.raises(ReservedPermission):
            await platform.authz.grants.add_grant(None, "role", BASE_ROLE_IDS["editor"], GrantSpec(key))
        with pytest.raises(ReservedPermission):
            await platform.authz.grants.add_grant(None, "group", group.id, GrantSpec(key))
        with pytest.raises(ValidationFailed):
            await platform.authz.grants.add_grant(None, "user", member, GrantSpec(key))


async def test_aggregation_never_reaches_admin_authority(platform: AuthzPlatform) -> None:
    reserved = set(await _reserved(platform))
    async with platform.database.session() as session:
        everything = list((await session.execute(select(Permission.key))).scalars())
    member = await insert_user(platform.database)
    custom = await platform.authz.grants.create_role(user(member), "almighty", "Almighty")
    group = await platform.authz.grants.create_group(user(member), "everyone", "Everyone")
    for key in everything:
        if key not in reserved:
            await platform.authz.grants.add_grant(None, "role", custom.id, GrantSpec(key))
            await platform.authz.grants.add_grant(None, "group", group.id, GrantSpec(key))
    await platform.authz.grants.assign_role(user(member), member, "custom:almighty")
    for role in ("support", "moderator", "editor"):
        await platform.authz.grants.assign_role(user(member), member, role)
    await platform.authz.grants.add_member(user(member), member, "everyone")
    for key in reserved:
        assert not await platform.authz.engine.is_allowed(user(member), key)
    assert await platform.authz.engine.is_allowed(user(member), "news.publish")


def test_plugins_cannot_declare_reserved_permissions() -> None:
    with pytest.raises(PermissionDeclarationError):
        PermissionRegistry().declare("plugin:x.admin", "x", owner="plugin:x", reserved=True)


async def test_base_roles_cannot_be_deleted(platform: AuthzPlatform) -> None:
    from portalab.core.errors import Conflict

    actor = user(await insert_user(platform.database))
    for key, role_id in BASE_ROLE_IDS.items():
        with pytest.raises(Conflict):
            await platform.authz.grants.delete_role(actor, role_id)
        assert key
