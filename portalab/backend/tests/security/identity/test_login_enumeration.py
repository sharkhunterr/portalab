"""002 T016 — non-enumerating sign-in (FR-006/008, SC-002, research R4)."""

import statistics
import time

import httpx
import pytest
from fastapi import FastAPI

from portalab.modules.identity.domain.state_machine import AccountState
from tests.integration.identity.helpers import PASSWORD, comparable, create_user, login, module_of

pytestmark = pytest.mark.integration


@pytest.fixture
async def accounts(app: FastAPI) -> None:
    module = module_of(app)
    await create_user(module, "alice")
    for login_, state in (
        ("bob", AccountState.SUSPENDED),
        ("carol", AccountState.PENDING_VERIFICATION),
        ("dave", AccountState.PENDING_DELETION),
    ):
        await create_user(module, login_, state=state)
    await create_user(module, "erin", password=None, state=AccountState.PENDING_VERIFICATION)


FAILURES = [
    ("nobody", PASSWORD),  # unknown login
    ("alice", "wrong password!"),  # wrong password
    ("bob", "wrong password!"),  # suspended + wrong password
    ("carol", "wrong password!"),  # pending verification + wrong password
    ("dave", "wrong password!"),  # pending deletion + wrong password
    ("erin", PASSWORD),  # account without credentials yet
    ("not a valid login!", PASSWORD),  # cannot even be a login
]


@pytest.mark.usefixtures("accounts")
async def test_all_unauthenticated_failures_are_identical(client: httpx.AsyncClient) -> None:
    answers = []
    for login_, password in FAILURES:
        response = await client.post("/api/v1/auth/login", json={"login": login_, "password": password})
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/problem+json")
        assert "set-cookie" not in response.headers
        answers.append(comparable(response.json()))
    assert all(answer == answers[0] for answer in answers)
    assert answers[0]["code"] == "auth.invalid_credentials"


@pytest.mark.usefixtures("accounts")
@pytest.mark.parametrize("login_", ["bob", "carol", "dave"])
async def test_state_is_disclosed_only_after_valid_credentials(
    client: httpx.AsyncClient, login_: str
) -> None:
    response = await client.post("/api/v1/auth/login", json={"login": login_, "password": PASSWORD})
    assert response.status_code == 403
    assert response.json()["code"] == "auth.account_unavailable"
    assert "set-cookie" not in response.headers


@pytest.mark.usefixtures("accounts")
async def test_valid_login_succeeds(client: httpx.AsyncClient) -> None:
    response = await login(client, "ALICE")  # login is case-insensitive
    assert response.status_code == 200
    me = await client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["login"] == "alice"


async def test_timing_of_unknown_login_matches_wrong_password(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    module = module_of(app)
    rounds = 6
    for index in range(rounds):
        await create_user(module, f"known{index}")

    async def measure(prefix: str) -> float:
        samples = []
        for index in range(rounds):  # one identifier per attempt: the throttle stays out of the measurement
            started = time.perf_counter()
            response = await client.post(
                "/api/v1/auth/login", json={"login": f"{prefix}{index}", "password": "wrong password!"}
            )
            samples.append(time.perf_counter() - started)
            assert response.status_code == 401
        return statistics.median(samples[1:])

    await measure("warmup")
    unknown = await measure("ghost")
    known = await measure("known")
    assert 0.4 < unknown / known < 2.5, (unknown, known)
