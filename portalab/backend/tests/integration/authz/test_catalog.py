"""003 T007 — catalog declaration: idempotent upsert, reserved metadata, plugin disable withdraws and
re-enable restores, default role grants seeded once (admins' removals are respected)."""

import pytest
from sqlalchemy import func, select

from portalab.core.permissions import PermissionDeclarationError, PermissionRegistry
from portalab.modules.authz.catalog.declare import set_plugin_permissions_enabled, sync_catalog
from portalab.modules.authz.catalog.sync import CatalogSync
from portalab.modules.authz.engine.engine import AuthorizationEngine
from portalab.modules.authz.grants.service import GrantSpec
from portalab.modules.authz.models import Grant, Permission
from tests.authz_fixtures import AuthzPlatform, insert_user, user


def _registry() -> PermissionRegistry:
    registry = PermissionRegistry()
    registry.declare("notes.read", "Read notes", default_roles=["user"])
    registry.declare("notes.purge", "Purge notes", sensitive=True, reserved=True)
    registry.declare(
        "plugin:weather.use", "Use the weather plugin", owner="plugin:weather", user_grantable=True
    )
    return registry


def _engine(platform: AuthzPlatform, registry: PermissionRegistry) -> AuthorizationEngine:
    return AuthorizationEngine(
        platform.database,
        CatalogSync(platform.database, registry),
        platform.authz.audit,
        platform.authz.engine.events,
    )


async def test_sync_is_idempotent_and_keeps_metadata(platform: AuthzPlatform) -> None:
    registry = _registry()
    async with platform.database.unit_of_work() as uow:
        assert await sync_catalog(uow.session, registry) == 3
    async with platform.database.unit_of_work() as uow:
        assert await sync_catalog(uow.session, registry) == 0
    async with platform.database.session() as session:
        purge = await session.get(Permission, "notes.purge")
        assert purge is not None and purge.reserved and purge.sensitive and purge.declared_by == "core"
        defaults = await session.scalar(
            select(func.count()).select_from(Grant).where(Grant.permission_key == "notes.read")
        )
    assert defaults == 1


async def test_removed_default_grant_is_not_reseeded(platform: AuthzPlatform) -> None:
    registry = _registry()
    async with platform.database.unit_of_work() as uow:
        await sync_catalog(uow.session, registry)
    async with platform.database.session() as session:
        grant_id = await session.scalar(select(Grant.id).where(Grant.permission_key == "notes.read"))
    await platform.authz.grants.remove_grant(None, grant_id)
    async with platform.database.unit_of_work() as uow:
        await sync_catalog(uow.session, registry)
    async with platform.database.session() as session:
        assert (
            await session.scalar(
                select(func.count()).select_from(Grant).where(Grant.permission_key == "notes.read")
            )
            == 0
        )


async def test_plugin_disable_withdraws_and_reenable_restores(platform: AuthzPlatform) -> None:
    registry = _registry()
    engine = _engine(platform, registry)
    member = await insert_user(platform.database)
    await engine.catalog.ensure()
    await platform.authz.grants.add_grant(
        None, "user", member, GrantSpec("plugin:weather.use"), source="marketplace"
    )
    assert await engine.is_allowed(user(member), "plugin:weather.use")
    async with platform.database.unit_of_work() as uow:
        assert await set_plugin_permissions_enabled(uow.session, "weather", False) == 1
    assert not await engine.is_allowed(user(member), "plugin:weather.use")
    async with platform.database.session() as session:  # data and grants are kept
        assert (
            await session.scalar(select(func.count()).select_from(Grant).where(Grant.holder_id == member))
            == 1
        )
    async with platform.database.unit_of_work() as uow:
        await set_plugin_permissions_enabled(uow.session, "weather", True)
    assert await engine.is_allowed(user(member), "plugin:weather.use")


def test_declaration_rules() -> None:
    registry = PermissionRegistry()
    with pytest.raises(PermissionDeclarationError):
        registry.declare("plugin:evil.all", "x", owner="plugin:evil", reserved=True)
    with pytest.raises(PermissionDeclarationError):
        registry.declare("plugin:other.use", "x", owner="plugin:evil")
    with pytest.raises(PermissionDeclarationError):
        registry.declare("users.godmode", "x", reserved=True, default_roles=["editor"])
    with pytest.raises(PermissionDeclarationError):
        registry.declare("users.bad", "x", default_roles=["admin"])
    with pytest.raises(PermissionDeclarationError):
        registry.declare("Bad Key", "x")
    registry.declare("notes.read", "Read")
    registry.declare("notes.read", "Read")  # identical re-declaration is idempotent
    with pytest.raises(PermissionDeclarationError):
        registry.declare("notes.read", "Read differently")
