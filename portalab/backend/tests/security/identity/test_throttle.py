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


def test_a_lookalike_login_is_the_same_key() -> None:
    """#276: the key folds the login like the account is looked up — full-width or mathematical letters
    reach the same account, so they count as the same attempts."""
    admin = throttle_key("admin", "192.0.2.0/24")
    assert throttle_key("\uff41\uff44\uff4d\uff49\uff4e", "192.0.2.0/24") == admin  # full-width
    assert throttle_key("\U0001d41a" + "dmin", "192.0.2.0/24") == admin  # mathematical bold


async def test_a_burst_sent_at_once_is_throttled_like_one_after_the_other(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    """#276: attempts on one key run one after the other — a burst cannot slip between the check and the
    count of failures."""
    import asyncio

    await create_user(module_of(app), "admin")
    answers = await asyncio.gather(
        *(
            client.post("/api/v1/auth/login", json={"login": login_, "password": "bad password!"})
            for login_ in ["admin", "ADMIN", "\uff41dmin"] * 5
        )
    )
    codes = [a.status_code for a in answers]
    assert codes.count(401) == FREE_ATTEMPTS and codes.count(429) == len(codes) - FREE_ATTEMPTS
