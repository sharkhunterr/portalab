"""027 — the welcome: on by default with the portal's own words; the guided tour is a step of its own,
done once, and each step done is said once (``user.onboarding_step_completed``, for the missions)."""

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from portalab.core.event_port import OutboxEvent
from tests.integration.identity.helpers import create_user, login, module_of

pytestmark = pytest.mark.integration


async def test_welcome_and_tour(app: FastAPI, client: httpx.AsyncClient) -> None:
    await create_user(module_of(app), "alex")
    await login(client, "alex")
    assert (await client.get("/api/v1/me/onboarding/welcome")).json() == {"enabled": True, "message": ""}
    for _ in range(2):
        done = await client.post("/api/v1/me/onboarding/tour/complete")
        assert done.status_code == 200
    assert {s["step"]: bool(s["completed_at"]) for s in done.json()}["tour"] is True
    async with module_of(app).ctx.database.session() as session:
        rows = await session.execute(
            select(OutboxEvent.event_metadata)
            .where(OutboxEvent.type == "user.onboarding_step_completed")
            .order_by(OutboxEvent.seq)
        )
        said = [metadata.get("step") for metadata in rows.scalars()]
    assert said == ["tour"]
    assert (await client.post("/api/v1/me/onboarding/unknown/complete")).status_code == 404


async def test_tour_completed_said_once(app: FastAPI, client: httpx.AsyncClient) -> None:
    await create_user(module_of(app), "bea")
    await login(client, "bea")
    for _ in range(2):
        assert (await client.post("/api/v1/me/onboarding/tours/stats/complete")).status_code == 204
    assert (await client.post("/api/v1/me/onboarding/tours/nope/complete")).status_code == 404
    async with module_of(app).ctx.database.session() as session:
        rows = await session.execute(
            select(OutboxEvent.event_metadata).where(OutboxEvent.type == "user.tour_completed")
        )
        assert [metadata.get("tour") for metadata in rows.scalars()] == ["stats"]
