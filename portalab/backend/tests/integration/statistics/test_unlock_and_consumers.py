"""017 T018/T020/T022/T029 — unlocks through stub ports (locked ⇒ hint only and no bucket read; permanent
unlocks persisted and announced once; campaign conditions re-lock; port failure fails closed); the same value
through the API, the dashboard widget, an internal call and an AI principal; cross-service partial states;
Wrapped snapshots (immutable, owner-only, community thresholds)."""

from datetime import timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from portalab.capabilities.health import SERVICE_STATE, ServiceStateView
from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.statistics import CAMPAIGNS, PROGRESSION, Period
from portalab.core.authz_port import Principal
from tests.integration.identity.helpers import create_user, login, module_of
from tests.integration.privacy.conftest import NOW
from tests.integration.statistics.conftest import StatsHarness

pytestmark = pytest.mark.integration

LOCKED = {
    "key": "media.secret_minutes",
    "title_key": "t",
    "domain": "media",
    "scope": "personal",
    "event_types": ["media.played"],
    "measure": {"kind": "sum", "field": "minutes"},
    "unlock": {"condition": {"kind": "level_at_least", "value": 5}},
}


class Progression:
    def __init__(self) -> None:
        self.levels: dict[UUID, int] = {}
        self.fail = False

    async def level(self, user_id: UUID) -> int:
        if self.fail:
            raise RuntimeError("013 down")
        return self.levels.get(user_id, 1)

    async def has_achievement(self, user_id: UUID, achievement: str) -> bool:
        return False


class Campaigns:
    active = True

    async def is_active(self, campaign: str) -> bool:
        return self.active


async def test_unlocks(app: FastAPI, client: httpx.AsyncClient, stats: StatsHarness) -> None:
    progression = Progression()
    capabilities = stats.ev.full.identity.capabilities
    capabilities.provide(PROGRESSION, progression, instance_ref="t", owner="module:gamification")
    alex = await create_user(module_of(app), "alex")
    await stats.publish(
        "media.played",
        {"minutes": 12, "genre": "rock", "service_id": "s1"},
        at=NOW - timedelta(hours=1),
        actor=alex,
    )
    await stats.define(LOCKED)
    await stats.dispatch()
    computed: list[str] = []
    original = stats.module.provider._compute

    async def spy(*args: object, **kwargs: object) -> object:
        computed.append("x")
        return await original(*args, **kwargs)  # type: ignore[arg-type]

    stats.module.provider._compute = spy  # type: ignore[method-assign]
    await login(client, "alex")
    locked = (await client.get("/api/v1/statistics/media.secret_minutes")).json()
    assert (
        locked["state"] == "locked"
        and locked["unlock_hint"] == "statistics:unlock.level_at_least"
        and locked["value"] is None
    )
    assert computed == []  # nothing computed while locked
    progression.levels[alex] = 5
    assert (await client.get("/api/v1/statistics/media.secret_minutes")).json()["value"] == 12
    progression.levels[alex] = 1  # levels never re-lock: the unlock is persisted
    assert (await client.get("/api/v1/statistics/media.secret_minutes")).json()["state"] == "available"
    async with stats.database.session() as session:
        unlocked = (
            await session.execute(
                text("SELECT count(*) FROM events.events WHERE type = 'statistics.unlocked'")
            )
        ).scalar()
        quarantined = (await session.execute(text("SELECT count(*) FROM events.quarantine"))).scalar()
    assert unlocked == 1 and quarantined == 0

    campaigns = Campaigns()
    capabilities.provide(CAMPAIGNS, campaigns, instance_ref="t", owner="module:campaigns")
    await stats.define(
        {
            **LOCKED,
            "key": "media.halloween",
            "unlock": {"condition": {"kind": "campaign_active", "value": "halloween"}},
        }
    )
    await stats.dispatch()
    assert (await client.get("/api/v1/statistics/media.halloween")).json()["state"] == "available"
    campaigns.active = False
    assert (await client.get("/api/v1/statistics/media.halloween")).json()["state"] == "locked"  # re-locks
    progression.fail = True
    await stats.define({**LOCKED, "key": "media.other_locked"})
    assert (await client.get("/api/v1/statistics/media.other_locked")).json()[
        "state"
    ] == "locked"  # fail closed
    catalog = {e["key"]: e for e in (await client.get("/api/v1/statistics/catalog")).json()}
    assert catalog["media.other_locked"]["locked"] and catalog["media.secret_minutes"]["locked"] is False


async def test_same_value_everywhere_and_cross_service(
    app: FastAPI, client: httpx.AsyncClient, stats: StatsHarness
) -> None:
    alex = await create_user(module_of(app), "alex")
    for days in (1, 2, 10):
        await stats.publish(
            "media.played",
            {"minutes": days, "genre": "rock", "service_id": "s1"},
            at=NOW - timedelta(days=days),
            actor=alex,
        )
    definition = {**LOCKED, "key": "media.mine", "unlock": None, "sources": ["s1", "s2"]}
    await stats.define(definition)
    await stats.dispatch()
    await login(client, "alex")
    api = (
        await client.get("/api/v1/statistics/media.mine", params={"period": "last_n_days", "days": 30})
    ).json()
    direct = await stats.module.provider.get(
        "media.mine", viewer=Principal(user_id=alex), period=Period("last_n_days", days=30)
    )
    ai = await stats.module.provider.get(
        "media.mine", viewer=Principal(channel="ai", acting_for=alex), period=Period("last_n_days", days=30)
    )
    widget = await stats.widgets.get("statistics.card").provider.load(
        Principal(user_id=alex), {"stat_key": "media.mine", "days": 30}, LocaleContext()
    )  # type: ignore[union-attr]
    assert api["value"] == direct.value == ai.value == widget.data["value"] == 13  # type: ignore[index]
    assert api["trend"]["previous_value"] == 0 and api["trend"]["percent"] is None
    assert api["state"] == "partial" and api["source_states"] == {"s1": "unknown", "s2": "unknown"}

    class Health:
        async def get(self, service_id: str) -> ServiceStateView:
            state = "unavailable" if service_id == "s2" else "operational"
            return ServiceStateView(service_id, state, NOW, NOW, 1.0, NOW)  # type: ignore[arg-type]

        async def all(self) -> list[ServiceStateView]:
            return []

    stats.ev.full.identity.capabilities.provide(
        SERVICE_STATE, Health(), instance_ref="t", owner="module:health"
    )
    partial = (await client.get("/api/v1/statistics/media.mine")).json()
    assert (
        partial["state"] == "partial"
        and partial["source_states"] == {"s1": "ok", "s2": "unavailable"}
        and partial["value"] == 13
    )
    too_long = await client.get(
        "/api/v1/statistics/media.mine", params={"period": "last_n_days", "days": 3000}
    )
    assert too_long.status_code == 422 and too_long.json()["code"] == "statistics.too_many_buckets"


async def test_wrapped(app: FastAPI, client: httpx.AsyncClient, stats: StatsHarness) -> None:
    alex = await create_user(module_of(app), "alex")
    await create_user(module_of(app), "sam")
    last_month = NOW.replace(day=1) - timedelta(days=3)
    await stats.publish(
        "media.played", {"minutes": 40, "genre": "rock", "service_id": "s1"}, at=last_month, actor=alex
    )
    for _ in range(5):
        await stats.publish(
            "media.played", {"minutes": 1, "genre": "rock", "service_id": "s1"}, at=last_month, actor=uuid4()
        )
    await stats.define({**LOCKED, "key": "media.mine", "unlock": None})
    await stats.define({**LOCKED, "key": "media.all", "unlock": None, "scope": "community"})
    await stats.dispatch()
    await stats.module.wrapped.save_definition("monthly", "month", ["media.mine", "media.all"])
    assert await stats.module.wrapped.generate() >= 2
    assert await stats.module.wrapped.generate() == 0  # idempotent
    await login(client, "alex")
    [mine] = (await client.get("/api/v1/me/wrapped")).json()
    assert [s["value"] for s in mine["payload"]["stats"]] == [40, 45]  # personal + community view
    await login(client, "sam")
    assert (await client.get(f"/api/v1/me/wrapped/{mine['id']}")).status_code == 404  # owner only
    community = (await client.get(f"/api/v1/wrapped/community/{mine['period_start']}")).json()
    assert community[0]["payload"]["stats"][0]["value"] == 45
    async with stats.database.session() as session:
        with pytest.raises(Exception, match="immutable"):
            await session.execute(text("UPDATE stats.wrapped_snapshots SET payload = '{}'"))
