"""017 T023 (#84) — the activity, community, requests and trends packs computed from their domains' real
event types: each member's own figures, the community's behind the privacy threshold, the requests split by
kind, and a trend's period-over-period change."""

from collections.abc import Sequence
from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from portalab.capabilities.events import default_event_types
from portalab.capabilities.statistics import PackRegistry, Period
from portalab.core.authz_port import Principal
from portalab.modules.community import permissions as _community_permissions  # noqa: F401 — community.read
from portalab.modules.community.proposals.types import register_slice_d_types
from portalab.modules.gamification.events import register_event_types as register_gamification
from portalab.modules.identity import event_types as _identity_types  # noqa: F401 — user.visited
from portalab.modules.marketplace.events import register_event_types as register_marketplace
from portalab.modules.media import permissions as _media_permissions  # noqa: F401 — media.request
from portalab.modules.media.events import register_event_types as register_media
from portalab.modules.statistics.packs.registry import register_builtin
from portalab.modules.support.events import register_event_types as register_support
from tests.authz_fixtures import insert_user
from tests.integration.privacy.conftest import NOW
from tests.integration.statistics.conftest import StatsHarness

pytestmark = pytest.mark.integration

MONTH = Period("last_n_days", days=30)


async def install(stats: StatsHarness, *domains: str) -> None:
    types = stats.ev.types
    for register in (
        register_slice_d_types,
        register_gamification,
        register_media,
        register_marketplace,
        register_support,
    ):
        register(types)
    visited = default_event_types.get("user.visited")
    assert visited is not None
    if types.get("user.visited") is None:
        types.register(visited)
    packs = PackRegistry()
    register_builtin(packs)
    for _, domain, definitions, _ in packs.packs():
        if domain in domains:
            for definition in definitions:
                await stats.define(definition.model_dump(mode="json"))


async def members(stats: StatsHarness, count: int) -> list[UUID]:
    return [await insert_user(stats.database) for _ in range(count)]


async def vote(stats: StatsHarness, voters: Sequence[UUID], *, days: int = 1) -> None:
    for voter in voters:
        await stats.publish(
            "project.vote_added",
            {"proposal": str(uuid4()), "count": 1},
            at=NOW - timedelta(days=days),
            actor=voter,
        )


async def test_community_and_activity_packs(stats: StatsHarness) -> None:
    await install(stats, "community", "activity")
    people = await members(stats, 5)
    alex = people[0]
    await vote(stats, people)
    await vote(stats, [alex], days=2)
    for who in people:
        await stats.publish("user.visited", {"day": "d"}, at=NOW - timedelta(hours=2), actor=who)
    await stats.publish(
        "quest.completed",
        {"quest": "q", "kind": "daily", "period": "p"},
        at=NOW - timedelta(hours=3),
        actor=alex,
    )
    await stats.dispatch()
    get = stats.module.provider.get

    votes = await get("community.votes_cast", viewer=Principal(user_id=people[1]), period=MONTH)
    assert votes.state == "available" and votes.value == 6
    mine = await get("community.my_votes", viewer=Principal(user_id=alex), period=MONTH)
    assert mine.value == 2
    assert (await get("activity.visits", viewer=Principal(user_id=alex), period=MONTH)).value == 5
    assert (await get("activity.member_actions", viewer=Principal(user_id=alex), period=MONTH)).value == 7
    assert (await get("activity.my_actions", viewer=Principal(user_id=alex), period=MONTH)).value == 3
    sam = await get("activity.my_actions", viewer=Principal(user_id=people[1]), period=MONTH)
    assert sam.value == 1  # only their own vote, never alex's


async def test_community_values_need_enough_members(stats: StatsHarness) -> None:
    await install(stats, "community")
    few = await members(stats, 2)
    await vote(stats, few)
    await stats.dispatch()
    votes = await stats.module.provider.get(
        "community.votes_cast", viewer=Principal(user_id=few[0]), period=MONTH
    )
    assert votes.state == "insufficient_data" and votes.value is None  # two voters could be recognized


async def test_requests_by_kind_and_trend(stats: StatsHarness) -> None:
    await install(stats, "requests", "trends")
    viewer = (await members(stats, 1))[0]
    for kind, days in (("movie", 1), ("movie", 2), ("tv", 3), ("movie", 9)):
        payload = {"request": str(uuid4()), "object": None, "kind": kind, "state": "pending"}
        await stats.publish("media.request_created", payload, at=NOW - timedelta(days=days))
    await stats.publish(
        "media.request_available",
        {"request": str(uuid4()), "object": None, "kind": "tv", "state": "available"},
        at=NOW - timedelta(days=1),
    )
    await stats.dispatch()
    get = stats.module.provider.get

    made = await get("requests.created", viewer=Principal(user_id=viewer), period=MONTH)
    assert made.value == 4
    assert {b["dims"]["kind"]: b["value"] for b in made.breakdown} == {"movie": 3, "tv": 1}
    fulfilled = await get("requests.fulfilled", viewer=Principal(user_id=viewer), period=MONTH)
    assert fulfilled.value == 1
    week = await get(
        "trends.requests", viewer=Principal(user_id=viewer), period=Period("last_n_days", days=7)
    )
    assert week.value == 3 and week.trend is not None
    assert week.trend.previous_value == 1 and week.trend.direction == "up"
