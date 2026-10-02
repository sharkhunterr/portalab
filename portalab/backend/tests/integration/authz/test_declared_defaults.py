"""003 T036 (F15) — per-module default role grants, plugin-scoped entitlement grants via the
``authz.user_grants`` capability (never reserved, allow-listed only), principal channels ai|automation."""

import pytest
from sqlalchemy import select

from portalab.capabilities.user_grants import CAPABILITY as USER_GRANTS
from portalab.core.errors import ValidationFailed
from portalab.core.permissions import PermissionRegistry
from portalab.modules.authz.catalog.sync import CatalogSync
from portalab.modules.authz.engine.engine import AuthorizationEngine
from portalab.modules.authz.models import BASE_ROLE_IDS, Grant
from tests.authz_fixtures import AuthzPlatform, ai, automation, insert_user, user


@pytest.fixture
async def engine(platform: AuthzPlatform) -> AuthorizationEngine:
    registry = PermissionRegistry()
    registry.declare("tickets.comment", "Comment tickets", default_roles=["user", ("support", "global")])
    registry.declare(
        "plugin:weather.use", "Use the weather plugin", owner="plugin:weather", user_grantable=True
    )
    registry.declare("media.request", "Request media", user_grantable=False, default_roles=[])
    catalog = CatalogSync(platform.database, registry)
    built = AuthorizationEngine(
        platform.database, catalog, platform.authz.audit, platform.authz.engine.events
    )
    await catalog.sync()
    return built


async def test_default_roles_apply_to_every_account(
    engine: AuthorizationEngine, platform: AuthzPlatform
) -> None:
    member = await insert_user(platform.database)
    assert await engine.is_allowed(user(member), "tickets.comment")
    assert not await engine.is_allowed(user(member), "media.request")


async def test_entitlement_grants_through_the_capability(
    engine: AuthorizationEngine, platform: AuthzPlatform
) -> None:
    member, other = await insert_user(platform.database), await insert_user(platform.database)
    grants = platform.identity.capabilities.system_providers(USER_GRANTS)[0].provider
    await grants.grant(member, "plugin:weather.use", source="marketplace")
    await grants.grant(member, "plugin:weather.use", source="marketplace")  # idempotent
    assert await engine.is_allowed(user(member), "plugin:weather.use")
    assert not await engine.is_allowed(user(other), "plugin:weather.use")
    assert await engine.is_allowed(automation(member), "plugin:weather.use")
    with pytest.raises(ValidationFailed):
        await grants.grant(member, "media.request", source="marketplace")  # not allow-listed
    with pytest.raises(ValidationFailed):
        await grants.grant(member, "users.admin.transfer", source="marketplace")  # reserved
    assert await grants.revoke(member, "plugin:weather.use") is True
    assert await grants.revoke(member, "plugin:weather.use") is False
    assert not await engine.is_allowed(user(member), "plugin:weather.use")


async def test_ai_channel_needs_ai_use_on_top(engine: AuthorizationEngine, platform: AuthzPlatform) -> None:
    member = await insert_user(platform.database)
    assert await engine.is_allowed(ai(member), "tickets.comment")  # ai.use is a default User grant
    async with platform.database.session() as session:
        grant_id = await session.scalar(
            select(Grant.id).where(Grant.permission_key == "ai.use", Grant.holder_id == BASE_ROLE_IDS["user"])
        )
    await platform.authz.grants.remove_grant(None, grant_id)
    assert not await engine.is_allowed(ai(member), "tickets.comment")
    assert await engine.is_allowed(automation(member), "tickets.comment")
