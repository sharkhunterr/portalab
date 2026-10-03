"""012 T019 — achievements and quests display: definitions and rewards come from 013 (``economy.catalog``;
Community stores none); hidden achievements reveal nothing until unlocked; another member's unlocked
achievements only per their visibility; challenges shown as time-boxed quests; progress is the viewer's
own only; 013 down ⇒ ``unavailable``."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from portalab.capabilities.economy import CATALOG, GamificationCatalog
from tests.integration.community.conftest import CoHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


@dataclass
class FakeCatalog:
    down: bool = False

    async def achievements_of(self, user_id: UUID) -> Sequence[dict[str, Any]]:
        if self.down:
            raise RuntimeError("013 is down")
        return [
            {"key": "night_owl", "state": "hidden", "label": "Night owl", "criteria": ["secret"]},
            {
                "key": "first",
                "state": "unlocked",
                "label": "First",
                "unlocked_at": "2026-10-01T12:00:00+00:00",
            },
            {"key": "ten", "state": "locked", "label": "Ten", "progress": [{"current": 3, "target": 10}]},
        ]

    async def unlocked_of(self, user_id: UUID, limit: int = 50) -> Sequence[dict[str, Any]]:
        return [{"key": "first", "label": "First", "unlocked_at": "2026-10-01T12:00:00+00:00"}]

    async def quests_of(self, user_id: UUID) -> Sequence[dict[str, Any]]:
        if self.down:
            raise RuntimeError("013 is down")
        return [
            {
                "key": "weekend",
                "kind": "challenge",
                "label": "Weekend",
                "period": "none",
                "period_key": "once",
                "starts_at": "2026-10-02T00:00:00+00:00",
                "ends_at": "2026-10-04T00:00:00+00:00",
                "completed_at": None,
                "steps": [{"event_type": "media.played", "current": 1, "target": 2}],
                "rewards": [{"value": "coins", "amount": 10}],
            },
            {
                "key": "daily_listen",
                "kind": "daily",
                "label": "Listen today",
                "period": "day",
                "period_key": "2026-10-01",
                "starts_at": None,
                "ends_at": None,
                "completed_at": "2026-10-01T12:00:00+00:00",
                "steps": [{"event_type": "media.played", "current": 1, "target": 1}],
                "rewards": [],
            },
        ]


async def test_views(co: CoHarness, client: AsyncClient) -> None:
    await login(client, "ursula")
    assert (await client.get("/api/v1/community/achievements")).json() == {
        "state": "unavailable",
        "items": [],
    }
    fake = FakeCatalog()
    assert isinstance(fake, GamificationCatalog)
    co.module.capabilities.provide(CATALOG, fake, instance_ref="fake013", owner="module:test")

    mine = (await client.get("/api/v1/community/achievements")).json()
    assert mine["state"] == "available"
    assert mine["items"][0] == {"key": "night_owl", "state": "hidden"}  # nothing revealed
    assert mine["items"][2]["progress"] == [{"current": 3, "target": 10}]

    ulrich = co.people["ulrich"]
    assert (
        await client.get("/api/v1/community/achievements", params={"member": str(ulrich)})
    ).status_code == 404
    await co.prefer("ulrich", "progression", "community")
    other = (await client.get("/api/v1/community/achievements", params={"member": str(ulrich)})).json()
    assert other["items"] == [
        {"key": "first", "state": "unlocked", "label": "First", "unlocked_at": "2026-10-01T12:00:00+00:00"}
    ]  # unlocked only, no progress
    await co.prefer("ulrich", "progression", "leaderboard")  # leaderboards-only is not a profile surface
    assert (
        await client.get("/api/v1/community/achievements", params={"member": str(ulrich)})
    ).status_code == 404

    quests = (await client.get("/api/v1/community/quests")).json()["items"]
    challenge, daily = quests
    assert challenge["kind"] == "challenge" and challenge["time_boxed"] and not challenge["completed"]
    assert challenge["steps"] == [{"current": 1, "target": 2}]
    assert daily["time_boxed"] is False and daily["completed"] is True

    fake.down = True
    assert (await client.get("/api/v1/community/quests")).json()["state"] == "unavailable"
    assert (await client.get("/api/v1/community/achievements")).json()["state"] == "unavailable"

    async with co.database.session() as session:
        tables = set(
            (
                await session.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'community'"))
            ).scalars()
        )
    assert not tables & {"achievements", "quests", "quest_progress", "rewards"}
