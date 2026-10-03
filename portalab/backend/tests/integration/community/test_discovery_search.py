"""012 T011 — discovery shelves (new members, projects, recent unlocks, activity highlights) are bound by
the same visibility as their source surface; an empty shelf offers a next action; unpermitted or private
items never surface; one failing shelf degrades alone."""

from datetime import timedelta

import pytest
from httpx import AsyncClient

from portalab.capabilities.community import DiscoveryShelf
from tests.integration.community.conftest import CoHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def test_shelves(co: CoHarness, client: AsyncClient) -> None:
    await login(client, "ulrich")
    listed = (await client.get("/api/v1/community/discovery")).json()
    assert [s["key"] for s in listed] == ["new_members", "projects", "recent_unlocks", "activity_highlights"]
    unlocks = (await client.get("/api/v1/community/discovery/recent_unlocks")).json()
    assert unlocks["state"] == "no-data" and unlocks["items"] == [] and unlocks["empty_action"]

    await co.emit("achievement.unlocked", "ursula", {"achievement": "first-steps"})
    co.clock.advance(timedelta(minutes=1))
    await co.emit("user.level_up", "ursula", {"level": 3})
    await co.prefer("vera", "community_activity", "private")
    await co.emit("achievement.unlocked", "vera", {"achievement": "first-steps"})
    unlocks = (await client.get("/api/v1/community/discovery/recent_unlocks")).json()
    assert [(i["actor_name"], i["kind"]) for i in unlocks["items"]] == [("Ursula", "achievement.unlocked")]
    highlights = (await client.get("/api/v1/community/discovery/activity_highlights")).json()
    assert [i["kind"] for i in highlights["items"]] == ["user.level_up"]

    await co.prefer("mona", "member_listing", "private")
    newest = (await client.get("/api/v1/community/discovery/new_members")).json()
    names = [i["display_name"] for i in newest["items"]]
    assert "Mona" not in names and set(names) == {"Boss", "Ursula", "Ulrich", "Vera"}

    async def broken(viewer: object, limit: int) -> list[dict[str, str]]:
        raise RuntimeError("down")

    co.module.shelves.register(DiscoveryShelf("broken", "module:test", broken, 99))
    assert (await client.get("/api/v1/community/discovery/broken")).json()["state"] == "unavailable"
    assert (await client.get("/api/v1/community/discovery/nope")).status_code == 404
