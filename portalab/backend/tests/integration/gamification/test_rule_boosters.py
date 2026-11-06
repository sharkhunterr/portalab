"""Issue 234 — a reward rule's boosters: its event's content's boosters given by the cards (once per member
and content), journaled as a value of their own beside XP, Contribution and Coins — in the journal, its
filter and the charts — and nothing journaled when none was given."""

from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from portalab.capabilities.media_core import CONTENT_BOOSTERS
from portalab.modules.media.events import register_event_types
from tests.integration.gamification.conftest import GamHarness
from tests.integration.gamification.test_play_kinds import sitting
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


class Cards:
    def __init__(self) -> None:
        self.given: set[tuple[UUID, UUID]] = set()
        self.among: list[tuple[UUID, dict[str, Any], str]] = []

    async def give(self, user: UUID, object_id: UUID, count: int, reason: str) -> int:
        if (user, object_id) in self.given:
            return 0  # once per member and content
        self.given.add((user, object_id))
        return count

    async def give_among(self, user: UUID, among: Any, count: int, reason: str) -> int:
        self.among.append((user, dict(among), reason))
        return count


async def test_a_rules_boosters_are_journaled(gm: GamHarness, client: AsyncClient) -> None:
    register_event_types(gm.ev.types)
    gm.module.capabilities.provide(CONTENT_BOOSTERS, Cards(), instance_ref="cards", owner="module:cards")
    await gm.rule(
        "film",
        {
            "event_type": "media.playback_finished",
            "label": "Film vu jusqu'au bout",
            "predicate": [{"field": "kind", "op": "eq", "value": "movie"}],
            "grants": [{"value": "xp", "amount": 30}],
            "boosters": 1,
        },
    )
    ursula = gm.people["ursula"]
    film: dict[str, Any] = sitting("movie", 6_000, object=str(uuid4()))
    finished = "media.playback_finished"
    await gm.module.pipeline.process(gm.envelope(ursula, film, event_type=finished))
    again = {**film, "session": str(uuid4())}  # seen again
    await gm.module.pipeline.process(gm.envelope(ursula, again, event_type=finished))

    await login(client, "ursula")
    journal = (await client.get("/api/v1/me/progression/operations?days=7")).json()
    rows = [(row["value"], row["delta"]) for row in journal["items"]]
    assert rows.count(("booster", 1)) == 1 and rows.count(("xp", 30)) == 2  # one booster for one film
    only = (await client.get("/api/v1/me/progression/operations?days=7&value=booster")).json()
    assert [(row["value"], row["balance"]) for row in only["items"]] == [("booster", 1)]
    sources = (await client.get("/api/v1/me/progression/sources?value=booster&days=7")).json()
    assert {s["source"]: s["amount"] for s in sources["sources"]} == {"movie": 1}


async def test_an_event_of_no_content_gives_the_boosters_of_the_works_it_names(gm: GamHarness) -> None:
    """Issue 356: the month's bingo filled is about no content — its booster draws among the works the event
    names (the card's genre); an event naming neither a content nor works gives none."""
    register_event_types(gm.ev.types)
    cards = Cards()
    gm.module.capabilities.provide(CONTENT_BOOSTERS, cards, instance_ref="cards", owner="module:cards")
    await gm.rule(
        "card",
        {
            "event_type": "media.playback_finished",
            "label": "Carton plein",
            "grants": [{"value": "xp", "amount": 200}],
            "boosters": 1,
        },
    )
    ursula = gm.people["ursula"]
    finished = "media.playback_finished"
    nothing = {k: v for k, v in sitting("movie", 6_000).items() if k != "object"}  # about no content
    named = {**nothing, "booster": {"genre": "scifi"}}
    await gm.module.pipeline.process(gm.envelope(ursula, named, event_type=finished))
    await gm.module.pipeline.process(gm.envelope(ursula, nothing, event_type=finished))
    assert [(user, among) for user, among, _ in cards.among] == [(ursula, {"genre": "scifi"})]
    assert cards.among[0][2].startswith("rule:card:")
