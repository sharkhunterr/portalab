"""002 T040 — deletion lifecycle: cancel before due; finalize runs every registered participant (one failing
once, retried); tombstone nulls PII and keeps the id; display name released; sole Admin refused."""

from datetime import timedelta
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select

from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY
from portalab.core.event_port import OutboxEvent
from portalab.core.jobs.models import Job
from portalab.core.time import FixedClock
from portalab.modules.identity.models import AccountStateHistory, Credential, User, UserSession
from portalab.modules.identity.services.deletion import SagaIncomplete
from tests.integration.identity.helpers import PASSWORD, create_user, login, make_admin, module_of

pytestmark = pytest.mark.integration


class FlakyParticipant:
    """Stands for another module (e.g. gamification destroying remaining Coins); fails on first call."""

    def __init__(self) -> None:
        self.calls: list[UUID] = []

    async def erase(self, user_id: UUID, mode: str) -> None:
        self.calls.append(user_id)
        if len(self.calls) == 1:
            raise ConnectionError("ledger temporarily unavailable")


async def _request(client: httpx.AsyncClient) -> httpx.Response:
    return await client.post("/api/v1/me/deletion", json={"password": PASSWORD})


async def test_request_then_cancel_within_grace(
    app: FastAPI, client: httpx.AsyncClient, clock: FixedClock
) -> None:
    module = module_of(app)
    user_id = await create_user(module, "alice")
    await login(client, "alice")
    wrong = await client.post("/api/v1/me/deletion", json={"password": "not my password"})
    assert wrong.status_code == 401  # step-up re-authentication

    response = await _request(client)
    assert response.status_code == 200 and response.json()["state"] == "pending_deletion"
    assert (await client.get("/api/v1/me")).status_code == 401  # every session revoked
    refused = await client.post("/api/v1/auth/login", json={"login": "alice", "password": PASSWORD})
    assert refused.status_code == 403 and "deletion_cancellable_until" in refused.json()

    clock.advance(timedelta(days=module.ctx.config.deletion_grace_days - 1))
    cancelled = await client.post(
        "/api/v1/auth/deletion/cancel", json={"login": "alice", "password": PASSWORD}
    )
    assert cancelled.status_code == 204
    async with module.ctx.database.session() as session:
        user = await session.get(User, user_id)
        assert user is not None and user.state == "active" and user.deletion_due_at is None
        events = list((await session.execute(select(OutboxEvent.type))).scalars())
    assert "user.deletion_requested" in events and "user.deletion_cancelled" in events
    assert (await login(client, "alice")).status_code == 200


async def test_cancel_is_impossible_after_the_grace_period(
    app: FastAPI, client: httpx.AsyncClient, clock: FixedClock
) -> None:
    module = module_of(app)
    await create_user(module, "bob")
    await login(client, "bob")
    await _request(client)
    clock.advance(timedelta(days=module.ctx.config.deletion_grace_days, seconds=1))
    late = await client.post("/api/v1/auth/deletion/cancel", json={"login": "bob", "password": PASSWORD})
    assert late.status_code == 409 and late.json()["code"] == "user.deletion_not_cancellable"


async def test_finalize_runs_participants_and_tombstones(
    app: FastAPI, client: httpx.AsyncClient, clock: FixedClock
) -> None:
    module = module_of(app)
    flaky = FlakyParticipant()
    module.ctx.capabilities.provide(
        ERASURE_CAPABILITY, flaky, instance_ref="gamification.coins", owner="test"
    )
    user_id = await create_user(module, "carol", display_name="Carol")
    await login(client, "carol")
    await client.put("/api/v1/me/avatar", content=_png(), headers={"Content-Type": "image/png"})
    await client.patch(
        "/api/v1/me/profile", json={"fields": {"bio": {"value": "about me", "visibility": "public"}}}
    )
    request = await _request(client)
    assert request.status_code == 200

    async with module.ctx.database.session() as session:
        job = (
            await session.execute(select(Job).where(Job.kind == "identity.finalize_deletion"))
        ).scalar_one()
    request_id = UUID(job.payload["request_id"])
    assert await module.deletion.finalize(request_id) is False  # not due yet

    clock.advance(timedelta(days=module.ctx.config.deletion_grace_days, seconds=1))
    with pytest.raises(SagaIncomplete):
        await module.deletion.finalize(request_id)
    assert await module.deletion.finalize(request_id) is True  # retry: the failed participant now succeeds
    assert await module.deletion.finalize(request_id) is True  # idempotent
    assert flaky.calls == [user_id, user_id]

    async with module.ctx.database.session() as session:
        user = await session.get(User, user_id)
        assert user is not None
        assert user.state == "deleted" and user.deleted_at is not None
        assert (user.login, user.login_display, user.display_name, user.display_name_key, user.email) == (
            None,
            None,
            None,
            None,
            None,
        )
        assert await session.scalar(select(func.count()).select_from(Credential)) == 0
        assert await session.scalar(select(func.count()).select_from(UserSession)) == 0
        history = await session.scalar(
            select(func.count())
            .select_from(AccountStateHistory)
            .where(AccountStateHistory.user_id == user_id)
        )
        assert history and history >= 3  # integrity history kept, same pseudonymous id
        events = list((await session.execute(select(OutboxEvent.type))).scalars())
    assert events.count("user.anonymized") == 1 and events.count("user.deleted") == 1

    # the display name is released: a new, distinct account may take it
    newcomer = await create_user(module, "carol2", display_name="Carol")
    assert newcomer != user_id
    directory = module.ctx.capabilities.system_providers("identity.directory")[0].provider
    summary = await directory.get_user_summary(user_id)
    assert summary.anonymized and summary.display_name is None and not summary.is_active


async def test_sole_admin_cannot_request_deletion(app: FastAPI, client: httpx.AsyncClient) -> None:
    module = module_of(app)
    admin_id = await make_admin(module)
    await login(client, "admin")
    refused = await _request(client)
    assert refused.status_code == 409 and refused.json()["code"] == "admin.sole_admin_protected"
    other = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://portal.test")
    async with other:
        response = await client.post(f"/api/v1/users/{admin_id}/deletion", json={"reason": "x"})
    assert response.status_code == 409
    async with module.ctx.database.session() as session:
        assert (await session.get(User, admin_id)).state == "active"  # type: ignore[union-attr]


async def test_admin_initiated_deletion_and_cancel(app: FastAPI, client: httpx.AsyncClient) -> None:
    module = module_of(app)
    await make_admin(module)
    user_id = await create_user(module, "dave")
    await login(client, "admin")
    requested = await client.post(f"/api/v1/users/{user_id}/deletion", json={"reason": "member_left"})
    assert requested.status_code == 200
    assert (await client.delete(f"/api/v1/users/{user_id}/deletion")).status_code == 204
    actions = module.ctx.audit.actions()  # type: ignore[attr-defined]
    assert "user.deletion_requested" in actions and "user.deletion_cancelled" in actions


def _png() -> bytes:
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), (1, 1, 1)).save(buffer, format="PNG")
    return buffer.getvalue()
