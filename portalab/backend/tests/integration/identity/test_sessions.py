"""002 T018 — idle/absolute expiry, ``revoke_all(user)``, tokens stored only as hashes."""

from datetime import timedelta

from sqlalchemy import select, text

from portalab.core.time import FixedClock
from portalab.modules.identity.models import UserSession
from portalab.modules.identity.module import IdentityModule
from portalab.modules.identity.services.sessions import SessionService, hash_token, ip_prefix
from portalab.modules.identity.settings import IdentityConfig
from tests.identity_fakes import IdentityHarness
from tests.integration.identity.helpers import create_user

CONFIG = IdentityConfig(session_idle_minutes=30, session_absolute_hours=2)


async def test_idle_expiry(harness: IdentityHarness, clock: FixedClock) -> None:
    module = IdentityModule(harness.context)
    user_id = await create_user(module, "alice")
    sessions = SessionService(CONFIG)
    db = harness.context.database
    async with db.unit_of_work() as uow:
        issued = await sessions.create(uow.session, user_id, clock.now())
    clock.advance(timedelta(minutes=29))
    async with db.unit_of_work() as uow:
        assert await sessions.resolve(uow.session, issued.token, clock.now()) is not None  # slides the expiry
    clock.advance(timedelta(minutes=29))
    async with db.unit_of_work() as uow:
        assert await sessions.resolve(uow.session, issued.token, clock.now()) is not None
    clock.advance(timedelta(minutes=31))
    async with db.unit_of_work() as uow:
        assert await sessions.resolve(uow.session, issued.token, clock.now()) is None


async def test_absolute_expiry_despite_activity(harness: IdentityHarness, clock: FixedClock) -> None:
    module = IdentityModule(harness.context)
    user_id = await create_user(module, "bob")
    sessions = SessionService(CONFIG)
    db = harness.context.database
    async with db.unit_of_work() as uow:
        issued = await sessions.create(uow.session, user_id, clock.now())
    for _ in range(7):  # 7 x 20 min = 2h20 of continuous activity
        clock.advance(timedelta(minutes=20))
        async with db.unit_of_work() as uow:
            alive = await sessions.resolve(uow.session, issued.token, clock.now())
    assert alive is None


async def test_revoke_all_for_user(harness: IdentityHarness, clock: FixedClock) -> None:
    module = IdentityModule(harness.context)
    alice = await create_user(module, "carol")
    other = await create_user(module, "dave")
    sessions = SessionService(CONFIG)
    db = harness.context.database
    async with db.unit_of_work() as uow:
        tokens = [(await sessions.create(uow.session, alice, clock.now())).token for _ in range(3)]
        other_token = (await sessions.create(uow.session, other, clock.now())).token
    async with db.unit_of_work() as uow:
        assert await sessions.revoke_all(uow.session, alice, clock.now(), "admin") == 3
    async with db.unit_of_work() as uow:
        for token in tokens:
            assert await sessions.resolve(uow.session, token, clock.now()) is None
        assert await sessions.resolve(uow.session, other_token, clock.now()) is not None


async def test_tokens_are_stored_only_as_hashes(harness: IdentityHarness, clock: FixedClock) -> None:
    module = IdentityModule(harness.context)
    user_id = await create_user(module, "erin")
    sessions = SessionService(CONFIG)
    db = harness.context.database
    async with db.unit_of_work() as uow:
        issued = await sessions.create(
            uow.session, user_id, clock.now(), user_agent="Mozilla/5.0 (X11)", client_ip="203.0.113.77"
        )
    async with db.session() as session:
        row = (await session.execute(select(UserSession))).scalar_one()
        assert row.token_hash == hash_token(issued.token) != issued.token
        assert row.ip_prefix == "203.0.113.0/24"
        assert row.user_agent_summary == "Mozilla/5.0"
        dump = (
            await session.execute(text("SELECT row_to_json(s)::text FROM identity.sessions s"))
        ).scalar_one()
    assert issued.token not in dump
    assert issued.csrf_token not in dump


def test_ip_prefix_truncation() -> None:
    assert ip_prefix("2001:db8:abcd:12::1") == "2001:db8:abcd::/48"
    assert ip_prefix("garbage") is None
    assert ip_prefix(None) is None
