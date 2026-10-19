"""Issue 160 — plays by kind: each sitting's kind (episode, film, audiobook…) is kept, so the progression's
sources, its journal and the plays' statistics show them apart — mine and, for the administrators,
everyone's; the plays rewarded before the change get their kind back from the event store."""

import importlib.util
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select, text

from portalab.modules.gamification.models import PlayKind
from portalab.modules.media.events import register_event_types
from tests.integration.gamification.conftest import GamHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration
MIGRATIONS = Path(__file__).resolve().parents[3] / "migrations" / "gamification" / "versions"

WATCH = {
    "event_type": "media.playback_finished",
    "grants": [{"value": "xp", "per_unit": {"field": "watched_s", "factor": 1 / 60, "max": 240}}],
}
WATCH_PARTIAL = {**WATCH, "event_type": "media.playback_abandoned"}
FILM_BONUS = {
    "event_type": "media.playback_finished",
    "predicate": [{"field": "kind", "op": "eq", "value": "movie"}],
    "grants": [{"value": "xp", "amount": 30}, {"value": "coins", "amount": 5}],
}


def sitting(kind: str, watched_s: float, **extra: Any) -> dict[str, Any]:
    return {
        "object": str(uuid4()),
        "kind": kind,
        "service": "plex",
        "session": str(uuid4()),
        "state_seq": 1,
        "position_s": watched_s,
        "duration_s": watched_s,
        "percent": 100.0,
        "occurred_at": "2026-10-19T10:00:00Z",
        "watched_s": watched_s,
        **extra,
    }


async def _setup(gm: GamHarness) -> None:
    register_event_types(gm.ev.types)
    await gm.rule("watch", WATCH)
    await gm.rule("watch_partial", WATCH_PARTIAL)
    await gm.rule("film_bonus", FILM_BONUS)


async def test_plays_show_by_kind(gm: GamHarness, client: AsyncClient) -> None:
    await _setup(gm)
    ursula, ulrich = gm.people["ursula"], gm.people["ulrich"]
    finished, abandoned = "media.playback_finished", "media.playback_abandoned"
    for user, kind, seconds, event_type in (
        (ursula, "episode", 1_800, finished),  # 30 XP
        (ursula, "episode", 1_200, finished),  # 20 XP
        (ursula, "movie", 6_000, finished),  # 100 XP + 30 XP and 5 Coins of bonus
        (ursula, "audiobook", 3_600, abandoned),  # 60 XP, not finished
        (ulrich, "episode", 600, finished),  # 10 XP
    ):
        await gm.module.pipeline.process(gm.envelope(user, sitting(kind, seconds), event_type=event_type))

    await login(client, "ursula")
    sources = (await client.get("/api/v1/me/progression/sources?value=xp&days=7")).json()
    assert {s["source"]: s["amount"] for s in sources["sources"]} == {
        "movie": 130,
        "audiobook": 60,
        "episode": 50,
    }
    plays = (await client.get("/api/v1/me/progression/plays?days=7")).json()
    by_kind = {line["play"]: line for line in plays["kinds"]}
    assert [line["play"] for line in plays["kinds"]] == ["movie", "audiobook", "episode"]  # by XP
    assert by_kind["episode"] | {"play": "episode"} == {
        "play": "episode",
        "sittings": 2,
        "finished": 2,
        "watched_s": 3_000,
        "xp": 50,
        "coins": 0,
        "members": 1,
    }
    assert by_kind["audiobook"]["finished"] == 0 and by_kind["movie"]["coins"] == 5
    assert sum(d["sittings"].get("episode", 0) for d in plays["days"]) == 2

    journal = (await client.get("/api/v1/me/progression/operations?days=7")).json()
    assert {item["play"] for item in journal["items"]} == {"episode", "movie", "audiobook"}
    assert {item["source"] for item in journal["items"]} == {"episode", "movie", "audiobook"}
    films = (await client.get("/api/v1/me/progression/operations?days=7&play=movie")).json()
    assert films["total"] == 3 and {item["play"] for item in films["items"]} == {"movie"}
    # the balances stay those of the whole ledger: 50 of episodes before the film, the audiobook after it
    balances = sorted(item["balance"] for item in films["items"])
    assert balances[0] == 5 and balances[-1] == 180 and balances[1] in (80, 150)  # whichever rule went first

    await login(client, "boss")
    everyone = (await client.get("/api/v1/admin/gamification/plays?days=7")).json()
    assert {line["play"]: line["members"] for line in everyone["kinds"]} == {
        "movie": 1,
        "audiobook": 1,
        "episode": 2,
    }
    one = (await client.get(f"/api/v1/admin/gamification/plays?days=7&member={ulrich}")).json()
    assert [(line["play"], line["xp"]) for line in one["kinds"]] == [("episode", 10)]


async def test_older_plays_get_their_kind_back(gm: GamHarness, client: AsyncClient) -> None:
    """The migration's back-fill: the plays rewarded before the change find their kind in the event store."""
    await _setup(gm)
    ursula = gm.people["ursula"]
    await gm.emit(ursula, sitting("movie", 600), event_type="media.playback_finished")
    async with gm.database.unit_of_work() as uow:
        assert await uow.session.scalar(select(PlayKind.kind)) == "movie"
        await uow.session.execute(delete(PlayKind))  # as before the change
    path = MIGRATIONS / "20261019_0900_gamification_0009_play_kinds.py"
    spec = importlib.util.spec_from_file_location("play_kinds_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    async with gm.database.unit_of_work() as uow:
        await uow.session.execute(text(migration.BACKFILL))
    async with gm.database.session() as session:
        restored = (await session.execute(select(PlayKind))).scalars().one()
    assert (restored.kind, restored.finished, restored.watched_s) == ("movie", True, 600)
    assert restored.occurred_at <= gm.clock.now() + timedelta(seconds=5)
