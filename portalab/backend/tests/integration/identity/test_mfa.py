"""Issue 408 — two-factor authentication: a member turns a TOTP second factor on (password asked again, a
first code confirms it), signing in then waits on a challenge with no session before the code, a code is
accepted once, a recovery code once, a challenge expires and stops after five wrong codes, ten wrong codes
in a quarter of an hour lock new challenges, and an administrator can lift a member's (never their own nor
the Admin's)."""

from datetime import timedelta
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select, update

from portalab.modules.identity.models import MfaChallenge, RecoveryCode, TotpFactor
from portalab.modules.identity.module import IdentityModule
from portalab.modules.identity.services.mfa import STEP, code_at, matching_step
from tests.integration.identity.helpers import PASSWORD, create_user, login, make_admin, module_of

pytestmark = pytest.mark.integration


def _step(module: IdentityModule, ahead: int = 0) -> int:
    return int(module.ctx.now().timestamp()) // STEP + ahead


async def _turn_on(client: httpx.AsyncClient, module: IdentityModule) -> tuple[str, list[str]]:
    setup = await client.post("/api/v1/me/mfa/setup", json={"password": PASSWORD})
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    done = await client.post("/api/v1/me/mfa/confirm", json={"code": code_at(secret, _step(module))})
    assert done.status_code == 200, done.text
    return secret, done.json()["codes"]


async def _first_step(client: httpx.AsyncClient, name: str) -> dict[str, Any]:
    response = await client.post("/api/v1/auth/login", json={"login": name, "password": PASSWORD})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def _second_step(client: httpx.AsyncClient, challenge: str, code: str) -> httpx.Response:
    response = await client.post("/api/v1/auth/login/mfa", json={"challenge": challenge, "code": code})
    if response.status_code == 200:
        client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return response


def test_totp_matches_rfc_6238() -> None:
    # RFC 6238 appendix B, SHA-1 secret "12345678901234567890", last six digits
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert code_at(secret, 59 // 30) == "287082"
    assert code_at(secret, 1111111109 // 30) == "081804"
    assert code_at(secret, 20000000000 // 30) == "353130"


def test_window_and_replay() -> None:
    from datetime import UTC, datetime

    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    now = datetime.fromtimestamp(1111111109, UTC)
    current = 1111111109 // 30
    assert matching_step(secret, code_at(secret, current), now, None) == current
    assert matching_step(secret, code_at(secret, current - 1), now, None) == current - 1  # a clock a bit off
    assert matching_step(secret, code_at(secret, current + 2), now, None) is None  # too far
    assert matching_step(secret, code_at(secret, current), now, current) is None  # used already
    assert matching_step(secret, "08 18 04", now, None) == current  # spaces as typed
    assert matching_step(secret, "12345", now, None) is None


async def test_turn_on_then_sign_in_in_two_steps(app: FastAPI, client: httpx.AsyncClient) -> None:
    module = module_of(app)
    alice = await create_user(module, "alice")
    await login(client, "alice")
    assert (await client.get("/api/v1/me/mfa")).json() == {"enabled": False, "recovery_codes_left": 0}

    wrong = await client.post("/api/v1/me/mfa/setup", json={"password": "nope"})
    assert wrong.status_code == 422 and wrong.json()["code"] == "identity.password_current_wrong"
    setup = await client.post("/api/v1/me/mfa/setup", json={"password": PASSWORD})
    body = setup.json()
    assert body["uri"].startswith("otpauth://totp/") and f"secret={body['secret']}" in body["uri"]
    assert body["qr_svg"].lstrip().startswith(("<?xml", "<svg"))
    async with module.ctx.database.session() as session:
        factor = await session.get(TotpFactor, alice)
    assert factor is not None and body["secret"] not in factor.secret  # kept encrypted
    assert not await module.mfa.enabled(alice)  # not in force before a first code

    bad = await client.post("/api/v1/me/mfa/confirm", json={"code": "000000"})
    assert bad.status_code == 422 and bad.json()["code"] == "auth.mfa_code_wrong"
    secret = body["secret"]
    done = await client.post("/api/v1/me/mfa/confirm", json={"code": code_at(secret, _step(module))})
    codes = done.json()["codes"]
    assert len(codes) == 10 and len(set(codes)) == 10
    async with module.ctx.database.session() as session:
        hashes = (await session.scalars(select(RecoveryCode.code_hash))).all()
    assert not set(codes) & set(hashes)  # only their hashes kept
    assert (await client.get("/api/v1/me/mfa")).json() == {"enabled": True, "recovery_codes_left": 10}
    again = await client.post("/api/v1/me/mfa/setup", json={"password": PASSWORD})
    assert again.status_code == 409 and again.json()["code"] == "auth.mfa_already_on"
    assert "identity.mfa_enabled" in module.ctx.audit.actions()  # type: ignore[attr-defined]

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://portal.test") as phone:
        first = await _first_step(phone, "alice")
        assert set(first) == {"mfa_required", "challenge", "expires_in"} and first["mfa_required"] is True
        assert not phone.cookies  # no session before the second factor
        assert (await phone.get("/api/v1/me")).status_code == 401
        replay = await _second_step(phone, first["challenge"], code_at(secret, _step(module)))
        assert replay.status_code == 422  # the code that confirmed the set-up is spent
        signed = await _second_step(phone, first["challenge"], code_at(secret, _step(module, 1)))
        assert signed.status_code == 200, signed.text
        assert (await phone.get("/api/v1/me")).status_code == 200
        reuse = await _second_step(phone, first["challenge"], code_at(secret, _step(module, 1)))
        assert reuse.status_code == 401 and reuse.json()["code"] == "auth.mfa_expired"  # challenge spent


async def test_recovery_code_once_and_challenge_limits(app: FastAPI, client: httpx.AsyncClient) -> None:
    module = module_of(app)
    bob = await create_user(module, "bob")
    await login(client, "bob")
    _, codes = await _turn_on(client, module)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="https://portal.test") as other:
        first = await _first_step(other, "bob")
        assert (await _second_step(other, first["challenge"], codes[0].upper())).status_code == 200
    async with httpx.AsyncClient(transport=transport, base_url="https://portal.test") as other:
        first = await _first_step(other, "bob")
        assert (await _second_step(other, first["challenge"], codes[0])).status_code == 422  # used once
    assert "auth.mfa_recovery_used" in module.ctx.audit.actions()  # type: ignore[attr-defined]
    assert (await client.get("/api/v1/me/mfa")).json()["recovery_codes_left"] == 9

    async with httpx.AsyncClient(transport=transport, base_url="https://portal.test") as other:
        first = await _first_step(other, "bob")
        for _ in range(5):
            assert (await _second_step(other, first["challenge"], "000000")).status_code == 422
        spent = await _second_step(other, first["challenge"], codes[1])
        assert spent.status_code == 401 and spent.json()["code"] == "auth.mfa_expired"  # five wrong codes

        late = await _first_step(other, "bob")
        async with module.ctx.database.unit_of_work() as uow:  # six minutes later
            await uow.session.execute(
                update(MfaChallenge)
                .where(MfaChallenge.user_id == bob, MfaChallenge.attempts == 0)
                .values(created_at=module.ctx.now() - timedelta(minutes=6))
            )
        expired = await _second_step(other, late["challenge"], codes[1])
        assert expired.status_code == 401 and expired.json()["code"] == "auth.mfa_expired"

        unknown = await _second_step(other, "not-a-challenge", codes[1])
        assert unknown.status_code == 401


async def test_ten_wrong_codes_lock_new_challenges(app: FastAPI, client: httpx.AsyncClient) -> None:
    module = module_of(app)
    await create_user(module, "carol")
    await login(client, "carol")
    await _turn_on(client, module)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://portal.test") as other:
        for _ in range(2):
            first = await _first_step(other, "carol")
            for _ in range(5):
                await _second_step(other, first["challenge"], "000000")
        locked = await other.post("/api/v1/auth/login", json={"login": "carol", "password": PASSWORD})
        assert locked.status_code == 429 and locked.json()["code"] == "auth.throttled"


async def test_turn_off_and_new_recovery_codes(app: FastAPI, client: httpx.AsyncClient) -> None:
    module = module_of(app)
    dan = await create_user(module, "dan")
    await login(client, "dan")
    secret, codes = await _turn_on(client, module)

    fresh = await client.post("/api/v1/me/mfa/recovery-codes", json={"password": PASSWORD})
    assert fresh.status_code == 200 and not set(fresh.json()["codes"]) & set(codes)  # the old ones void
    no_code = await client.post("/api/v1/me/mfa/off", json={"password": PASSWORD, "code": "000000"})
    assert no_code.status_code == 422 and no_code.json()["code"] == "auth.mfa_code_wrong"
    old = await client.post("/api/v1/me/mfa/off", json={"password": PASSWORD, "code": codes[0]})
    assert old.status_code == 422
    bad_password = await client.post(
        "/api/v1/me/mfa/off", json={"password": "nope", "code": code_at(secret, _step(module, 1))}
    )
    assert bad_password.status_code == 422
    assert bad_password.json()["code"] == "identity.password_current_wrong"
    off = await client.post(
        "/api/v1/me/mfa/off", json={"password": PASSWORD, "code": code_at(secret, _step(module, 1))}
    )
    assert off.status_code == 204, off.text
    assert not await module.mfa.enabled(dan)
    async with module.ctx.database.session() as session:
        assert (await session.scalars(select(RecoveryCode).where(RecoveryCode.user_id == dan))).all() == []
    assert "csrf_token" in (await _first_step(client, "dan"))  # a password alone signs in again


async def test_admin_lifts_a_member_second_factor(app: FastAPI, client: httpx.AsyncClient) -> None:
    module = module_of(app)
    admin_id = await make_admin(module)
    erin = await create_user(module, "erin")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://portal.test") as hers:
        await login(hers, "erin")
        await _turn_on(hers, module)

    await login(client, "admin")
    url = f"/api/v1/users/{erin}/mfa/off"
    wrong = await client.post(url, json={"password": "nope"})
    assert wrong.status_code == 422 and wrong.json()["code"] == "identity.password_current_wrong"
    own = await client.post(f"/api/v1/users/{admin_id}/mfa/off", json={"password": PASSWORD})
    assert own.status_code == 409 and own.json()["code"] == "auth.mfa_own_account"
    done = await client.post(url, json={"password": PASSWORD})
    assert done.status_code == 204, done.text
    assert not await module.mfa.enabled(erin)
    assert "identity.mfa_lifted" in module.ctx.audit.actions()  # type: ignore[attr-defined]


async def test_a_member_cannot_lift_nor_touch_the_admin(app: FastAPI, client: httpx.AsyncClient) -> None:
    module = module_of(app)
    admin_id = await make_admin(module)
    frank: UUID = await create_user(module, "frank")
    await create_user(module, "gina")
    await login(client, "gina")
    forbidden = await client.post(f"/api/v1/users/{frank}/mfa/off", json={"password": PASSWORD})
    assert forbidden.status_code == 403
    admin_side = await client.post(f"/api/v1/users/{admin_id}/mfa/off", json={"password": PASSWORD})
    assert admin_side.status_code == 403
