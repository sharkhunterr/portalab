"""003 T027 — confirmation tokens: single use, expiring, bound to principal + permission + resource +
payload hash; replay refused."""

from datetime import timedelta

from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.time import FixedClock
from portalab.modules.authz.confirmation.service import ConfirmationService
from tests.authz_fixtures import AuthzPlatform, ai, insert_user, user


async def test_single_use_and_bound(platform: AuthzPlatform, clock: FixedClock) -> None:
    service = ConfirmationService(platform.database, ttl_seconds=60, clock=clock)
    alice, bob = await insert_user(platform.database), await insert_user(platform.database)
    resource = ResourceRef("news", "42")
    token = await service.issue(user(alice), "news.delete", resource, {"hard": True})
    assert not await service.consume(token, user(bob), "news.delete", resource, {"hard": True})  # wrong user
    assert not await service.consume(token, user(alice), "news.delete", resource, {"hard": True})  # burnt
    token = await service.issue(user(alice), "news.delete", resource, {"hard": True})
    assert not await service.consume(token, user(alice), "news.delete", resource, {"hard": False})  # payload
    token = await service.issue(user(alice), "news.delete", resource, {"hard": True})
    assert not await service.consume(
        token, user(alice), "news.delete", ResourceRef("news", "43"), {"hard": True}
    )
    token = await service.issue(ai(alice), "news.delete", resource, {"hard": True})
    assert await service.consume(token, ai(alice), "news.delete", resource, {"hard": True})  # acting user
    assert not await service.consume(token, ai(alice), "news.delete", resource, {"hard": True})  # replay


async def test_expiry(platform: AuthzPlatform, clock: FixedClock) -> None:
    service = ConfirmationService(platform.database, ttl_seconds=60, clock=clock)
    alice = await insert_user(platform.database)
    token = await service.issue(user(alice), "economy.manage", None, {"rate": 2})
    clock.advance(timedelta(seconds=61))
    assert not await service.consume(token, user(alice), "economy.manage", None, {"rate": 2})


async def test_anonymous_cannot_confirm(platform: AuthzPlatform) -> None:
    import pytest

    from portalab.modules.authz.confirmation.service import ConfirmationRequired

    with pytest.raises(ConfirmationRequired):
        await ConfirmationService(platform.database).issue(Principal(), "news.delete", None, {})


async def test_decision_exposes_requires_confirmation(platform: AuthzPlatform) -> None:
    from tests.authz_fixtures import make_admin

    admin = await insert_user(platform.database)
    await make_admin(platform, admin)
    decision = await platform.authz.engine.authorize(user(admin), "news.delete")
    assert decision.allowed and decision.requires_confirmation
    assert not (await platform.authz.engine.authorize(user(admin), "news.read")).requires_confirmation
