"""002 T027 — ``create_first_admin`` succeeds once; refuses when an Admin exists;
concurrent calls ⇒ one winner."""

import asyncio

import pytest
from sqlalchemy import func, select

from portalab.capabilities.admin_authority import CAPABILITY
from portalab.core.errors import Conflict, Unavailable
from portalab.modules.identity.models import User
from portalab.modules.identity.module import IdentityModule
from tests.identity_fakes import IdentityHarness
from tests.integration.identity.helpers import PASSWORD


async def test_first_admin_once(harness: IdentityHarness) -> None:
    module = IdentityModule(harness.context)
    admin_id = await module.bootstrap.create_first_admin(login="root", password=PASSWORD, display_name="Root")
    assert harness.authority.admin == admin_id
    assert "admin.bootstrapped" in harness.audit.actions()
    with pytest.raises(Conflict) as caught:
        await module.bootstrap.create_first_admin(login="second", password=PASSWORD)
    assert caught.value.code == "admin.already_exists"
    async with harness.context.database.session() as session:
        assert await session.scalar(select(func.count()).select_from(User)) == 1
        user = await session.get(User, admin_id)
        assert user is not None and user.state == "active" and user.verified_at is not None


async def test_concurrent_bootstraps_have_one_winner(harness: IdentityHarness) -> None:
    module = IdentityModule(harness.context)
    results = await asyncio.gather(
        *(module.bootstrap.create_first_admin(login=f"root{i}", password=PASSWORD) for i in range(5)),
        return_exceptions=True,
    )
    winners = [result for result in results if not isinstance(result, BaseException)]
    losers = [result for result in results if isinstance(result, Conflict)]
    assert len(winners) == 1 and len(losers) == 4
    assert harness.authority.admin == winners[0]
    async with harness.context.database.session() as session:
        assert await session.scalar(select(func.count()).select_from(User)) == 1


async def test_bootstrap_fails_closed_without_the_authorization_module(harness: IdentityHarness) -> None:
    harness.context.capabilities.unregister("module:authz")
    assert harness.context.capabilities.system_providers(CAPABILITY) == []
    module = IdentityModule(harness.context)
    with pytest.raises(Unavailable):
        await module.bootstrap.create_first_admin(login="root", password=PASSWORD)
