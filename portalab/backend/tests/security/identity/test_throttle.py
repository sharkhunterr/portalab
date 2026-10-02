"""002 T019 — progressive delay per (identifier, ip prefix); never a hard lockout (research R5)."""

from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI

from portalab.core.time import FixedClock
from portalab.modules.identity.services.throttle import (
    FREE_ATTEMPTS,
    MAX_DELAY,
    LoginThrottleService,
    delay_after,
    throttle_key,
)
from tests.integration.identity.helpers import PASSWORD, create_user, login, module_of

pytestmark = pytest.mark.integration


def test_delay_is_progressive_and_capped() -> None:
    delays = [delay_after(n) for n in range(1, 40)]
    assert all(d == timedelta(0) for d in delays[: FREE_ATTEMPTS - 1])
    assert delays == sorted(delays)
    assert max(delays) == MAX_DELAY


async def test_failures_then_throttled_then_recovers(
    app: FastAPI, client: httpx.AsyncClient, clock: FixedClock
) -> None:
    await create_user(module_of(app), "admin")
    for _ in range(FREE_ATTEMPTS):
        response = await client.post(
            "/api/v1/auth/login", json={"login": "admin", "password": "bad password!"}
        )
        assert response.status_code == 401
    blocked = await client.post("/api/v1/auth/login", json={"login": "admin", "password": PASSWORD})
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "auth.throttled"
    assert blocked.json()["retry_after_seconds"] >= 1

    # another identifier from the same network is not affected
    unknown = await client.post("/api/v1/auth/login", json={"login": "someone", "password": "bad password!"})
    assert unknown.status_code == 401

    clock.advance(MAX_DELAY + timedelta(seconds=1))
    assert (await login(client, "admin")).status_code == 200


async def test_the_admin_is_never_hard_locked(app: FastAPI, clock: FixedClock) -> None:
    module = module_of(app)
    throttle = LoginThrottleService()
    key = throttle_key("admin", "198.51.100.0/24")
    for _ in range(200):  # a sustained attack
        async with module.ctx.database.unit_of_work() as uow:
            until = await throttle.record_failure(uow.session, key, clock.now())
        assert until is None or until - clock.now() <= MAX_DELAY
    clock.advance(MAX_DELAY)
    async with module.ctx.database.unit_of_work() as uow:
        assert await throttle.blocked_until(uow.session, key, clock.now()) is None
    # the attacker's network does not block the Admin's own network
    async with module.ctx.database.unit_of_work() as uow:
        assert (
            await throttle.blocked_until(uow.session, throttle_key("admin", "192.0.2.0/24"), clock.now())
            is None
        )


def test_keys_hide_the_identifier() -> None:
    key = throttle_key("Admin", "192.0.2.0/24")
    assert "admin" not in key and len(key) == 64
    assert key == throttle_key("admin ", "192.0.2.0/24")
