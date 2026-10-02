"""002 T014/T015 — AccountService transitions are atomic (state + history + event + audit) and the
``identity.directory`` capability reports active-account eligibility."""

import pytest
from sqlalchemy import func, select

from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.core.authz_port import Principal
from portalab.core.event_port import OutboxEvent
from portalab.modules.identity.domain.state_machine import AccountState, StateTransitionForbidden
from portalab.modules.identity.models import AccountStateHistory, User
from portalab.modules.identity.services.account_service import AccountService
from portalab.modules.identity.services.common import SYSTEM, DisplayNameTaken, admin_actor
from portalab.modules.identity.services.directory import register_directory
from tests.identity_fakes import IdentityHarness


async def _create(
    harness: IdentityHarness, login: str, name: str, state: AccountState = AccountState.ACTIVE
) -> User:
    service = AccountService(harness.context)
    async with harness.context.database.unit_of_work() as uow:
        return await service.create_user(
            uow.session, login=login, display_name=name, email=None, state=state, actor=SYSTEM, reason="test"
        )


async def test_create_writes_history_event_and_profile(harness: IdentityHarness) -> None:
    user = await _create(harness, "Alice", "Alice")
    async with harness.context.database.session() as session:
        stored = await session.get(User, user.id)
        assert stored is not None
        assert (stored.login, stored.login_display, stored.display_name_key) == ("alice", "Alice", "alice")
        history = (await session.execute(select(AccountStateHistory))).scalars().all()
        assert [(h.from_state, h.to_state, h.transition_seq) for h in history] == [(None, "active", 1)]
        events = (await session.execute(select(OutboxEvent.type, OutboxEvent.subject_id))).all()
        assert [tuple(e) for e in events] == [("user.created", str(user.id))]


async def test_duplicate_display_name_is_rejected(harness: IdentityHarness) -> None:
    await _create(harness, "alice", "Alice")
    with pytest.raises(DisplayNameTaken):
        await _create(harness, "alice2", "ALICE")


async def test_transition_is_atomic_and_deduplicated(harness: IdentityHarness) -> None:
    user = await _create(harness, "bob", "Bob")
    admin = admin_actor(Principal(user_id=user.id))  # actor identity is irrelevant for the guard
    service = AccountService(harness.context)
    async with harness.context.database.unit_of_work() as uow:
        locked = await service.get_for_update(uow.session, user.id)
        event = await service.transition(uow.session, locked, AccountState.SUSPENDED, admin, reason="abuse")
    assert event == "user.suspended"
    assert "user.suspended" in harness.audit.actions()
    assert harness.audit.records[-1].sensitive is True
    async with harness.context.database.session() as session:
        stored = await session.get(User, user.id)
        assert stored is not None and stored.state == "suspended" and stored.transition_seq == 2
        keys = (
            (await session.execute(select(OutboxEvent.dedup_key).order_by(OutboxEvent.seq))).scalars().all()
        )
        assert keys[-1] == f"user:{user.id}:suspended:2"


async def test_forbidden_transition_rolls_back_everything(harness: IdentityHarness) -> None:
    user = await _create(harness, "carol", "Carol")
    service = AccountService(harness.context)
    with pytest.raises(StateTransitionForbidden):
        async with harness.context.database.unit_of_work() as uow:
            locked = await service.get_for_update(uow.session, user.id)
            await service.transition(uow.session, locked, AccountState.SUSPENDED, SYSTEM, reason="nope")
    async with harness.context.database.session() as session:
        assert (await session.get(User, user.id)).state == "active"  # type: ignore[union-attr]
        count = await session.scalar(select(func.count()).select_from(AccountStateHistory))
        assert count == 1


async def test_audit_failure_refuses_a_sensitive_transition(harness: IdentityHarness) -> None:
    user = await _create(harness, "dora", "Dora")
    harness.audit.fail = True
    service = AccountService(harness.context)
    with pytest.raises(Exception, match="audited"):
        async with harness.context.database.unit_of_work() as uow:
            locked = await service.get_for_update(uow.session, user.id)
            await service.transition(
                uow.session,
                locked,
                AccountState.SUSPENDED,
                admin_actor(Principal(user_id=user.id)),
                reason="x",
            )
    async with harness.context.database.session() as session:
        assert (await session.get(User, user.id)).state == "active"  # type: ignore[union-attr]


async def test_directory_capability(harness: IdentityHarness) -> None:
    register_directory(harness.context.capabilities, harness.context)
    directory = harness.context.capabilities.system_providers(DIRECTORY)[0].provider
    active = await _create(harness, "erin", "Erin")
    pending = await _create(harness, "fred", "Fred", AccountState.PENDING_VERIFICATION)
    assert await directory.is_active_account(active.id) is True
    assert await directory.is_active_account(pending.id) is False
    assert await directory.exists(pending.id) is True
    summary = await directory.get_user_summary(active.id)
    assert summary is not None and summary.display_name == "Erin" and summary.is_active
    from uuid import uuid4

    assert await directory.get_user_summary(uuid4()) is None
    assert await directory.is_active_account(uuid4()) is False
