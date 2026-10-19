"""Plays by kind (issue 160): over a period, each kind of play — episodes, films, live TV, books, audiobooks,
music… — with its sittings, the works finished, the time watched (listened to, read), the XP and Coins it
earned (bonuses included) and, for the administrators, how many members; day by day too. A member's own, or
everyone's."""

from collections import defaultdict
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Date, cast, func, select

from portalab.core.db import Database
from portalab.modules.gamification.models import LedgerTransaction, PlayKind
from portalab.modules.gamification.progression.sources import GAINS, PLAY_KINDS, play_source


async def plays(database: Database, user: UUID | None, since: datetime, zone: str) -> dict[str, Any]:
    day = cast(func.timezone(zone, PlayKind.occurred_at), Date)
    window = [PlayKind.occurred_at >= since] + ([PlayKind.user_id == user] if user is not None else [])
    earned = (
        select(
            LedgerTransaction.trigger_event_id.label("event_id"),
            func.sum(LedgerTransaction.delta).filter(LedgerTransaction.value == "xp").label("xp"),
            func.sum(LedgerTransaction.delta).filter(LedgerTransaction.value == "coins").label("coins"),
        )
        .join(PlayKind, PlayKind.event_id == LedgerTransaction.trigger_event_id)
        .where(LedgerTransaction.delta > 0, LedgerTransaction.kind.in_(GAINS), *window)
        .group_by(LedgerTransaction.trigger_event_id)
        .subquery()
    )
    query = (
        select(
            day,
            PlayKind.kind,
            PlayKind.user_id,
            PlayKind.finished,
            PlayKind.watched_s,
            func.coalesce(earned.c.xp, 0),
            func.coalesce(earned.c.coins, 0),
        )
        .outerjoin(earned, earned.c.event_id == PlayKind.event_id)
        .where(*window)
    )
    async with database.session() as session:
        rows = (await session.execute(query)).all()
    totals: dict[str, dict[str, Any]] = {}
    members: dict[str, set[UUID]] = defaultdict(set)
    per_day: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for when, kind, owner, finished, watched, xp, coins in rows:
        play = play_source(kind)
        line = totals.setdefault(
            play, {"play": play, "sittings": 0, "finished": 0, "watched_s": 0, "xp": 0, "coins": 0}
        )
        line["sittings"] += 1
        line["finished"] += 1 if finished else 0
        line["watched_s"] += int(watched or 0)
        line["xp"] += int(xp or 0)
        line["coins"] += int(coins or 0)
        members[play].add(owner)
        per_day[when.isoformat()][play] += 1
    order = {play: index for index, play in enumerate(PLAY_KINDS)}
    kinds = sorted(totals.values(), key=lambda line: (-line["xp"], order.get(line["play"], 99)))
    for line in kinds:
        line["members"] = len(members[line["play"]])
    return {
        "kinds": kinds,
        "days": [{"day": d, "sittings": dict(counts)} for d, counts in sorted(per_day.items())],
    }
