"""002 T026 — registration (policy-gated, non-enumerating), Admin-created accounts (CD-036), verification
(token expiry, single use) → Active with ``user.created``/``user.verified`` and onboarding started."""

from dataclasses import replace
from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from portalab.core.event_port import OutboxEvent
from portalab.core.time import FixedClock
from portalab.modules.identity.jobs import verification_expiry
from portalab.modules.identity.models import User, VerificationToken
from tests.integration.identity.helpers import PASSWORD, comparable, login, make_admin, module_of


def _open(app: FastAPI) -> None:
    module = module_of(app)
    module.ctx.config = replace(module.ctx.config, registration_mode="open")


class CapturingChannel:
    def __init__(self) -> None:
        self.tokens: dict[str, str] = {}

    async def deliver(self, user_id, token, expires_at) -> None:  # type: ignore[no-untyped-def]
        self.tokens[str(user_id)] = token


@pytest.fixture
def channel(app: FastAPI) -> CapturingChannel:
    capture = CapturingChannel()
    module_of(app).registration.channel = capture
    return capture


async def _events(app: FastAPI) -> list[str]:
    async with module_of(app).ctx.database.session() as session:
        return list((await session.execute(select(OutboxEvent.type).order_by(OutboxEvent.seq))).scalars())


async def test_invite_only_refuses_self_registration(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register", json={"login": "eve", "display_name": "Eve", "password": PASSWORD}
    )
    assert response.status_code == 403
    assert response.json()["code"] == "auth.registration_closed"


async def test_open_registration_then_verify(
    app: FastAPI, client: httpx.AsyncClient, channel: CapturingChannel
) -> None:
    _open(app)
    response = await client.post(
        "/api/v1/auth/register", json={"login": "Eve", "display_name": "Eve", "password": PASSWORD}
    )
    assert response.status_code == 202
    (token,) = channel.tokens.values()
    assert (await login(client, "eve")).status_code == 403  # pending verification, valid credentials

    verified = await client.post("/api/v1/auth/verify", json={"token": token})
    assert verified.status_code == 204
    replay = await client.post("/api/v1/auth/verify", json={"token": token})
    assert replay.status_code == 400 and replay.json()["code"] == "auth.invalid_token"

    assert (await login(client, "eve")).status_code == 200
    me = (await client.get("/api/v1/me")).json()
    assert me["state"] == "active"
    assert {step["step"] for step in me["onboarding"]} == {
        "profile",
        "interests",
        "notifications",
        "privacy",
        "dashboard",
        "discovery",
        "tour",
    }
    events = await _events(app)
    assert events[:2] == ["user.created", "user.verified"]


async def test_registration_does_not_reveal_existing_logins(
    app: FastAPI, client: httpx.AsyncClient, channel: CapturingChannel
) -> None:
    _open(app)
    first = await client.post(
        "/api/v1/auth/register", json={"login": "zoe", "display_name": "Zoe", "password": PASSWORD}
    )
    again = await client.post(
        "/api/v1/auth/register", json={"login": "ZOE", "display_name": "Zoe Two", "password": PASSWORD}
    )
    assert first.status_code == again.status_code == 202
    assert first.json() == again.json()
    assert len(channel.tokens) == 1
    async with module_of(app).ctx.database.session() as session:
        assert len((await session.execute(select(User))).scalars().all()) == 1


async def test_duplicate_display_name_is_actionable(
    app: FastAPI, client: httpx.AsyncClient, channel: CapturingChannel
) -> None:
    _open(app)
    await client.post(
        "/api/v1/auth/register", json={"login": "ann", "display_name": "Ann", "password": PASSWORD}
    )
    clash = await client.post(
        "/api/v1/auth/register", json={"login": "ann2", "display_name": "ANN", "password": PASSWORD}
    )
    assert clash.status_code == 409
    assert clash.json()["code"] == "user.display_name_taken"


async def test_password_policy(app: FastAPI, client: httpx.AsyncClient) -> None:
    _open(app)
    weak = await client.post(
        "/api/v1/auth/register", json={"login": "bea", "display_name": "Bea", "password": "short"}
    )
    assert weak.status_code == 422
    assert weak.json()["code"] == "user.password_invalid"


async def test_admin_created_account_sets_password_at_verification(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    await make_admin(module_of(app))
    assert (await login(client, "admin")).status_code == 200
    created = await client.post("/api/v1/users", json={"login": "Paul", "display_name": "Paul"})
    assert created.status_code == 201
    token = created.json()["verification_token"]
    duplicate = await client.post("/api/v1/users", json={"login": "paul", "display_name": "Paul B"})
    assert duplicate.status_code == 409 and duplicate.json()["code"] == "user.login_taken"

    anonymous = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://portal.test")
    async with anonymous:
        missing = await anonymous.post("/api/v1/auth/verify", json={"token": token})
        assert missing.status_code == 422 and missing.json()["code"] == "user.password_required"
        assert (
            await anonymous.post("/api/v1/auth/verify", json={"token": token, "password": PASSWORD})
        ).status_code == 204
        assert (await login(anonymous, "paul")).status_code == 200


async def test_reissue_supersedes_previous_token(app: FastAPI, client: httpx.AsyncClient) -> None:
    await make_admin(module_of(app))
    await login(client, "admin")
    created = (await client.post("/api/v1/users", json={"login": "rita", "display_name": "Rita"})).json()
    reissued = await client.post(f"/api/v1/users/{created['user_id']}/verification")
    assert reissued.status_code == 200
    old = await client.post(
        "/api/v1/auth/verify", json={"token": created["verification_token"], "password": PASSWORD}
    )
    assert old.status_code == 400
    new = await client.post(
        "/api/v1/auth/verify", json={"token": reissued.json()["verification_token"], "password": PASSWORD}
    )
    assert new.status_code == 204


async def test_token_expiry_and_lifecycle_job(
    app: FastAPI, client: httpx.AsyncClient, clock: FixedClock
) -> None:
    module = module_of(app)
    await make_admin(module)
    await login(client, "admin")
    created = (await client.post("/api/v1/users", json={"login": "sam", "display_name": "Sam"})).json()
    clock.advance(timedelta(hours=module.ctx.config.verification_ttl_hours, seconds=1))
    expired = await client.post(
        "/api/v1/auth/verify", json={"token": created["verification_token"], "password": PASSWORD}
    )
    assert expired.status_code == 400
    assert comparable(expired.json())["code"] == "auth.invalid_token"

    assert await verification_expiry.run(module.ctx, module.deletion) == 1
    async with module.ctx.database.session() as session:
        user = await session.get(User, created["user_id"])
        assert user is not None and user.state == "pending_deletion"
        assert user.state_before_deletion == "pending_verification"
        tokens = (await session.execute(select(VerificationToken))).scalars().all()
        assert len(tokens) == 1
    assert await verification_expiry.run(module.ctx, module.deletion) == 0
