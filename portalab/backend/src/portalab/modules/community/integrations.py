"""Integrations (T015, T024): the dashboard widgets ``community.activity`` (009) — the latest feed entries
the viewer may see, under the same read-time visibility as the feed itself — ``community.projects``
(REQ-018: proposals open for votes or funding) and ``community.leaderboard`` (issue 189: the community's
podium and ranking, as the leaderboards page shows them)."""

from collections.abc import Mapping
from typing import Any

from portalab.capabilities.dashboard import (
    Refresh,
    Size,
    SizeLimits,
    WidgetDefinition,
    WidgetPayload,
    with_styles,
)
from portalab.capabilities.economy import PERIODS
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Principal
from portalab.core.time import Clock, utc_now
from portalab.modules.community.feed.service import FeedService
from portalab.modules.community.permissions import READ

OWNER = "module:community"

ACTIVITY_WIDGET = WidgetDefinition(
    key="community.activity",
    owner=OWNER,
    title_key="community:widget.activity.title",
    description_key="community:widget.activity.description",
    icon="users",
    required_permission=READ,
    size=SizeLimits(default=Size(4, 3), min=Size(3, 1), max=Size(8, 6)),
    refresh=Refresh(mode="interval", interval_s=300),
    stale_after_s=900,
    component_id="community.activity",
)


class ActivityWidget:
    def __init__(self, feed: FeedService, clock: Clock | None = None, looks: Any = None) -> None:
        self.feed = feed
        self.clock = clock
        self.looks = looks  # #127: async (UUID) -> the frame and name style a member wears

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        items, _ = await self.feed.page(principal, limit=8)
        if not items:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        return WidgetPayload(
            "available",
            as_of=utc_now(self.clock),
            data={
                "items": [
                    {
                        "id": str(i.id),
                        "actor_id": str(i.actor_id),
                        "actor_name": i.actor_name,
                        "anonymous": i.anonymous,  # issue 120
                        "look": None if i.anonymous or self.looks is None else await self.looks(i.actor_id),
                        "text_key": i.text_key,
                        "kind": i.kind,  # 027: what the widget names it by (as the feed does)
                        "params": i.params,
                        "occurred_at": i.occurred_at.isoformat(),
                    }
                    for i in items
                ]
            },
        )


PROJECTS_WIDGET = WidgetDefinition(
    key="community.projects",
    owner=OWNER,
    title_key="community:widget.projects.title",
    description_key="community:widget.projects.description",
    icon="lightbulb",
    required_permission=READ,
    size=SizeLimits(default=Size(4, 3), min=Size(3, 1), max=Size(8, 6)),
    refresh=Refresh(mode="interval", interval_s=600),
    stale_after_s=1800,
    component_id="community.projects",
)


class ProjectsWidget:
    def __init__(self, proposals: Any, votes: Any, clock: Clock | None = None) -> None:
        self.proposals = proposals
        self.votes = votes
        self.clock = clock

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        items = await self.proposals.needing_support(5)
        if not items:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        counts = await self.votes.counts([p.id for p in items])
        return WidgetPayload(
            "available",
            as_of=utc_now(self.clock),
            data={
                "items": [
                    {
                        "id": str(p.id),
                        "title": p.title,
                        "kind": p.kind,
                        "help_wanted": p.help_wanted,
                        "votes": counts.get(p.id, 0),
                    }
                    for p in items
                ]
            },
        )


LEADERBOARD_METRICS = ("xp", "coins", "achievements", "contribution", "level")
LEADERBOARD_ROWS = 10  # the podium and the table under it; my place comes apart when lower
LEADERBOARD_WIDGET = WidgetDefinition(
    key="community.leaderboard",
    owner=OWNER,
    title_key="community:widget.leaderboard.title",
    description_key="community:widget.leaderboard.description",
    icon="trophy",
    required_permission=READ,
    config_schema={
        "type": "object",
        "properties": {
            "metric": {"type": "string", "enum": list(LEADERBOARD_METRICS)},
            "period": {"type": "string", "enum": list(PERIODS)},
        },
    },
    config_defaults={"metric": "xp", "period": "month"},
    size=SizeLimits(default=Size(6, 4), min=Size(3, 1), max=Size(12, 8)),
    refresh=Refresh(mode="interval", interval_s=600),
    stale_after_s=1800,
    component_id="community.leaderboard",
)


def _rank(member: Any) -> dict[str, Any]:
    return {
        "rank": member.rank,
        "user_id": str(member.user_id),
        "display_name": member.display_name,
        "score": member.score,
        "me": member.me,
        "change": member.change,
        "new": member.new,
        "anonymous": member.anonymous,
        "look": member.look,
    }


class LeaderboardWidget:
    """Issue 189: the first ten of a leaderboard (its metric and period set in the widget's settings, the
    period changed in the widget too), my place, and how many are ranked (« 3 / 8 »)."""

    def __init__(self, leaderboards: Any, clock: Clock | None = None) -> None:
        self.leaderboards = leaderboards
        self.clock = clock

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        metric = str(config.get("metric") or "xp")
        period = "all" if metric == "level" else str(config.get("period") or "month")
        if metric not in self.leaderboards.metrics():
            return WidgetPayload("unavailable", as_of=utc_now(self.clock))
        view = await self.leaderboards.board(principal, metric, period, limit=100)
        if view.state == "unavailable":
            return WidgetPayload("unavailable", as_of=utc_now(self.clock))
        if not view.entries:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        return WidgetPayload(
            "available",
            as_of=utc_now(self.clock),
            data={
                "metric": metric,
                "period": period,
                "entries": [_rank(e) for e in view.entries[:LEADERBOARD_ROWS]],
                "me": _rank(view.me) if view.me else None,
                "total": len(view.entries),
            },
        )


ACTIVITY_WIDGET = with_styles(ACTIVITY_WIDGET, "live")  # 027 (#31)
