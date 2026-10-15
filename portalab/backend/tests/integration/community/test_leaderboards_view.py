"""012 T017 — the community leaderboards view delegates metrics, periods, ranking, opt-out and visibility to
013's ``economy.leaderboards`` (a recording fake honouring the contract here; the real ranking and
visibility rules are covered by 013's own tests), adds display names only, always returns the viewer's own
position, and degrades to ``unavailable`` without breaking when 013 is down or absent."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

import pytest
from httpx import AsyncClient

from portalab.capabilities.economy import LEADERBOARDS, LeaderboardEntry, LeaderboardPeriod, LeaderboardView
from portalab.core.authz_port import Principal
from portalab.core.errors import NotFound
from tests.integration.community.conftest import CoHarness
from tests.integration.identity.helpers import login
from tests.integration.privacy.conftest import NOW

pytestmark = pytest.mark.integration


@dataclass
class FakeLeaderboards:
    """013 as Community sees it: ranks are already visibility-filtered for the viewer."""

    ranking: list[tuple[UUID, int]] = field(default_factory=list)
    hidden: set[UUID] = field(default_factory=set)
    down: bool = False
    calls: list[tuple[str, str]] = field(default_factory=list)

    def metrics(self) -> Sequence[str]:
        return ["xp", "level"]

    async def board(
        self, viewer: Principal, metric: str, period: LeaderboardPeriod = "all", *, limit: int = 50
    ) -> LeaderboardView:
        self.calls.append((metric, period))
        if self.down:
            raise RuntimeError("013 is down")
        if metric not in self.metrics():
            raise NotFound("No such leaderboard.", code="economy.leaderboard_not_found")
        visible = [(u, s) for u, s in self.ranking if u == viewer.user_id or u not in self.hidden]
        entries = [LeaderboardEntry(i + 1, u, s, u == viewer.user_id) for i, (u, s) in enumerate(visible)]
        me = next((e for e in entries if e.me), None)
        return LeaderboardView(metric, period, NOW, tuple(entries[:limit]), me)


async def test_delegation_names_and_own_position(co: CoHarness, client: AsyncClient) -> None:
    await login(client, "ulrich")
    assert (await client.get("/api/v1/community/leaderboards")).json() == []
    absent = (await client.get("/api/v1/community/leaderboards/xp")).json()
    assert absent["state"] == "unavailable" and absent["entries"] == []

    fake = FakeLeaderboards([(co.people["ursula"], 60), (co.people["boss"], 40), (co.people["ulrich"], 20)])
    fake.hidden = {co.people["boss"]}
    co.module.capabilities.provide(LEADERBOARDS, fake, instance_ref="fake013", owner="module:test")
    assert (await client.get("/api/v1/community/leaderboards")).json() == ["xp", "level"]
    body = (await client.get("/api/v1/community/leaderboards/xp", params={"period": "week"})).json()
    assert body["state"] == "available" and fake.calls[-1] == ("xp", "week")
    assert [(e["rank"], e["display_name"], e["score"], e["me"]) for e in body["entries"]] == [
        (1, "Ursula", 60, False),
        (2, "Ulrich", 20, True),
    ]
    assert body["me"]["rank"] == 2
    position = (await client.get("/api/v1/community/me/position", params={"metric": "xp"})).json()
    assert position == {"metric": "xp", "period": "all", "state": "available", "rank": 2, "score": 20}
    assert (await client.get("/api/v1/community/leaderboards/coins")).status_code == 404
    assert (
        await client.get("/api/v1/community/leaderboards/xp", params={"period": "decade"})
    ).status_code == 422  # #128: a period it does not know

    fake.down = True
    down = await client.get("/api/v1/community/leaderboards/xp")
    assert down.status_code == 200 and down.json()["state"] == "unavailable"
    assert (await client.get("/api/v1/community/me/position")).json()["rank"] is None


def test_fake_is_a_reader() -> None:
    from portalab.capabilities.economy import LeaderboardReader

    assert isinstance(FakeLeaderboards(), LeaderboardReader)


class FakeCosmetics:
    """#127: what each member wears (the Marketplace's cosmetics as Community reads them)."""

    def __init__(self, worn: dict[UUID, dict[str, object]]) -> None:
        self.worn = worn

    async def sold(self, kind: str, field: str) -> frozenset[str]:
        return frozenset()

    async def owned(self, user_id: UUID, kind: str, field: str) -> frozenset[str]:
        return frozenset()

    async def equipped(self, user: UUID) -> dict[str, object]:
        return self.worn.get(user, {})


async def test_each_member_wears_their_frame_and_name_style(co: CoHarness, client: AsyncClient) -> None:
    from portalab.capabilities.themes import COSMETICS

    await login(client, "ulrich")
    ursula, boss = co.people["ursula"], co.people["boss"]
    co.module.capabilities.provide(
        LEADERBOARDS,
        FakeLeaderboards([(ursula, 60), (boss, 40)]),
        instance_ref="fake013",
        owner="module:test",
    )
    worn = {ursula: {"frame": "gold", "name": "wizard", "banner": "dunes"}}
    co.module.capabilities.provide(
        COSMETICS, FakeCosmetics(worn), instance_ref="fake027", owner="module:test"
    )
    body = (await client.get("/api/v1/community/leaderboards/xp", params={"period": "year"})).json()
    looks = {e["user_id"]: e["look"] for e in body["entries"]}
    assert looks[str(ursula)] == {"frame": "gold", "name": "wizard"}  # only what shows beside a name
    assert looks[str(boss)] == {"frame": None, "name": None}
