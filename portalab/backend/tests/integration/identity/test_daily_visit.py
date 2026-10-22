"""027: « came today » — ``user.visited`` once a day: at the sign-in, then at the first request of each new
day of a session kept open; never twice the same day."""

from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from portalab.core.time import FixedClock
from tests.integration.identity.helpers import create_user, login, module_of

pytestmark = pytest.mark.integration


async def visits(app: FastAPI) -> list[str]:
    async with module_of(app).ctx.database.session() as session:
        rows = await session.execute(
            text("SELECT metadata->>'day' FROM core.event_outbox WHERE type = 'user.visited' ORDER BY seq")
        )
        return [r[0] for r in rows]


async def test_one_visit_a_day_even_signed_in_for_days(
    app: FastAPI, client: httpx.AsyncClient, clock: FixedClock
) -> None:
    await create_user(module_of(app), "alice")
    await login(client, "alice")
    first = await visits(app)
    assert len(first) == 1
    clock.advance(timedelta(hours=1))
    assert (await client.get("/api/v1/me")).status_code == 200
    assert await visits(app) == first  # the same day: no second visit
    clock.advance(timedelta(days=1))
    assert (await client.get("/api/v1/me")).status_code == 200  # still signed in, the next day
    clock.advance(timedelta(minutes=5))
    assert (await client.get("/api/v1/me")).status_code == 200
    days = await visits(app)
    assert len(days) == 2 and days[0] != days[1]
