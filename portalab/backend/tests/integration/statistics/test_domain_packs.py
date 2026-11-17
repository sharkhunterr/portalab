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
    for kind, days in (("movie", 1), ("movie", 2), ("tv", 3), ("movie", 9), ("tv", 13)):
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
    assert made.value == 5
    assert {b["dims"]["kind"]: b["value"] for b in made.breakdown} == {"movie": 3, "tv": 2}
    fulfilled = await get("requests.fulfilled", viewer=Principal(user_id=viewer), period=MONTH)
    assert fulfilled.value == 1
    week = await get(
        "trends.requests", viewer=Principal(user_id=viewer), period=Period("last_n_days", days=7)
    )
    assert week.value == 3 and week.trend is not None
    assert week.trend.previous_value == 2 and week.trend.direction == "up"
    # issue 482: the previous week's days laid on this week's, drawn in grey under them
    assert len(week.previous_series) == 7
    assert [p["day"] for p in week.previous_series] == [
        str(week.period_start + timedelta(days=i)) for i in range(7)
    ]
    by_then = {p["previous_day"]: p["value"] for p in week.previous_series}
    assert (
        by_then[str((NOW - timedelta(days=9)).date())] == 1
        and by_then[str((NOW - timedelta(days=13)).date())] == 1
    )
    assert sum(p["value"] for p in week.previous_series) == 2
    # issue 479: a previous period the statistic did not cover yet (its first event inside it) — no trend
    short = await get(
        "trends.requests", viewer=Principal(user_id=viewer), period=Period("last_n_days", days=10)
    )
    assert short.value == 4 and short.trend is None and not short.previous_series  # nothing to draw


async def test_achievements_count_once_per_member_and_manual_xp_apart(stats: StatsHarness) -> None:
    """Issue 479: an achievement a member unlocks again counts once; the XP administrators add by hand is
    told apart from the XP the community earns."""
    await install(stats, "trends")
    people = await members(stats, 5)
    for who in people:
        await stats.publish(
            "achievement.unlocked", {"achievement": "regular"}, at=NOW - timedelta(days=1), actor=who
        )
        await stats.publish(
            "reward.granted",
            {"value": "xp", "amount": 10, "source": "daily"},
            at=NOW - timedelta(days=1),
            actor=who,
        )
        await stats.publish(
            "reward.granted",
            {"value": "xp", "amount": 1000, "source": "manual"},
            at=NOW - timedelta(days=1),
            actor=who,
        )
    alex = people[0]
    # alex's progress reset then earned again, and one more achievement of theirs
    await stats.publish(
        "achievement.unlocked", {"achievement": "regular"}, at=NOW - timedelta(days=2), actor=alex
    )
    await stats.publish(
        "achievement.unlocked", {"achievement": "saver"}, at=NOW - timedelta(days=3), actor=alex
    )
    await stats.dispatch()
    get = stats.module.provider.get
    viewer = Principal(user_id=alex)
    assert (await get("trends.achievements_unlocked", viewer=viewer, period=MONTH)).value == 6  # not 7
    assert (await get("trends.xp_earned", viewer=viewer, period=MONTH)).value == 50  # without the manual XP
    assert (await get("trends.xp_granted", viewer=viewer, period=MONTH)).value == 5000  # told apart


async def test_a_builtin_pack_change_replaces_the_running_version(stats: StatsHarness) -> None:
    """Issue 479: a built-in pack fixed in a release runs at once, recomputed from the history — unless an
    administrator runs their own version of it."""
    from portalab.modules.statistics.models import DefinitionStatus
    from portalab.modules.statistics.packs.registry import OWNER

    await install(stats, "trends")
    for days in (1, 2):
        await stats.publish(
            "media.request_created",
            {"request": str(uuid4()), "object": None, "kind": "movie", "state": "pending"},
            at=NOW - timedelta(days=days),
        )
    await stats.dispatch()
    base = {
        "key": "trends.fixed",
        "title_key": "statistics:stat.trends_requests.title",
        "domain": "trends",
        "scope": "community",
        "event_types": ["media.request_created"],
        "measure": {"kind": "count"},
        "required_permission": "statistics.read",
    }

    async def running() -> int | None:
        async with stats.database.session() as session:
            status = await session.get(DefinitionStatus, "trends.fixed")
            return status.active_version if status is not None else None

    stats.module.packs.register("fixed", [base], owner=OWNER)
    await stats.module.install_packs()
    assert await running() == 1
    stats.module.packs.register("fixed", [{**base, "viz": {"type": "bar"}}], owner=OWNER)
    await stats.module.install_packs()
    assert await running() == 2  # the release's fix runs
    await stats.module.install_packs()
    assert await running() == 2  # unchanged: no new version
    own = await stats.module.definitions.save(None, {**base, "viz": {"type": "area"}}, source="admin")
    await stats.module.activate(Principal(channel="system"), "trends.fixed", own)
    stats.module.packs.register("fixed", [{**base, "viz": {"type": "pie"}}], owner=OWNER)
    await stats.module.install_packs()
    assert await running() == own  # the administrator's version stays


async def test_personal_figures_count_the_member_an_event_is_about(stats: StatsHarness) -> None:
    """Issue 481: a ticket, a game launched on a media server — about a member without being acted by them —
    count in that member's own figures (they stayed empty)."""
    await install(stats, "support", "gaming", "activity")
    alex, sam = await members(stats, 2)
    await stats.publish(
        "ticket.created",
        {"ticket": str(uuid4()), "seq": 1, "state": "new", "type": "bug", "priority": "normal"},
        at=NOW - timedelta(days=1),
        about=alex,
    )
    for kind in ("game", "game", "movie"):
        await stats.publish(
            "media.playback_started",
            {
                "kind": kind,
                "service": "s",
                "session": str(uuid4()),
                "state_seq": 0,
                "position_s": 0.0,
                "occurred_at": (NOW - timedelta(days=2)).isoformat(),
            },
            at=NOW - timedelta(days=2),
            about=alex,
        )
    await stats.dispatch()
    get = stats.module.provider.get
    assert (await get("support.my_tickets", viewer=Principal(user_id=alex), period=MONTH)).value == 1
    assert (await get("gaming.my_games_started", viewer=Principal(user_id=alex), period=MONTH)).value == 2
    assert (
        await get("support.my_tickets", viewer=Principal(user_id=sam), period=MONTH)
    ).value == 0  # not theirs


async def test_a_builtin_statistic_no_longer_shipped_is_retired(stats: StatsHarness) -> None:
    """Issue 481: a figure a release stops shipping (told elsewhere) leaves the catalog — not an
    administrator's own version."""
    from portalab.modules.statistics.models import DefinitionStatus
    from portalab.modules.statistics.packs.registry import OWNER

    base = {
        "title_key": "statistics:stat.trends_requests.title",
        "domain": "trends",
        "scope": "community",
        "event_types": ["media.request_created"],
        "measure": {"kind": "count"},
        "required_permission": "statistics.read",
    }
    await install(stats, "trends")
    stats.module.packs.register(
        "old", [{**base, "key": "trends.kept"}, {**base, "key": "trends.gone"}], owner=OWNER
    )
    await stats.module.install_packs()
    own = await stats.module.definitions.save(None, {**base, "key": "trends.mine"}, source="admin")
    await stats.module.activate(Principal(channel="system"), "trends.mine", own)
    stats.module.packs.register("old", [{**base, "key": "trends.kept"}], owner=OWNER)
    await stats.module.install_packs()
    async with stats.database.session() as session:
        states = {
            k: (await session.get(DefinitionStatus, k)).status
            for k in ("trends.kept", "trends.gone", "trends.mine")
        }  # type: ignore[union-attr]
    assert states == {"trends.kept": "active", "trends.gone": "retired", "trends.mine": "active"}
