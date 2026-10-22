"""A title someone asked for, watched by another member: the asker's gain, and in the administration's
journal who watched; the member's own journal never names them."""

import pytest
from httpx import AsyncClient

from portalab.capabilities.events import EventType
from tests.integration.gamification.conftest import GamHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def test_the_journal_names_the_viewer_for_the_administration_only(
    gm: GamHarness, client: AsyncClient
) -> None:
    if gm.ev.types.get("media.request_watched") is None:
        gm.ev.types.register(EventType("media.request_watched", "test:media", rewardable=frozenset({"kind"})))
    await gm.rule(
        "request_watched",
        {
            "event_type": "media.request_watched",
            "grants": [{"value": "xp", "amount": 5}, {"value": "coins", "amount": 2}],
        },
    )
    asker, viewer = gm.people["ursula"], gm.people["ulrich"]
    payload = {"request": "r1", "object": "o1", "kind": "movie", "viewer": str(viewer)}
    await gm.emit(asker, payload, event_type="media.request_watched")

    await login(client, "boss")
    team = (await client.get("/api/v1/admin/gamification/operations?days=30")).json()["items"]
    gains = [i for i in team if i["user_id"] == str(asker)]
    assert {i["value"] for i in gains} == {"xp", "coins"}
    assert {i["other"] for i in gains} == {"ulrich"}

    await login(client, "ursula")
    mine = (await client.get("/api/v1/me/progression/operations?days=30")).json()["items"]
    assert mine and all(i.get("other") is None for i in mine)
