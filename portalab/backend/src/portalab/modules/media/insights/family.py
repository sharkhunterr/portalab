"""Issue 428: a household's dashboard — each member's watching, reading and playing lately.

Minutes, sittings and titles finished over the last days, by kind of media, day by day; the days in a row
with something watched (to today, or to yesterday while today is still young); the last title. A profile
watching at home through its master's account counts with its master (the service knows one account); what
it watches in the portal's own player and reader counts as its own.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.core.db import Database
from portalab.modules.media.models import Activity

LOOK_BACK_DAYS = 60  # the streak's horizon
FINISHED = 0.9


@dataclass
class MemberActivity:
    user_id: UUID
    minutes: int = 0
    plays: int = 0
    finished: int = 0
    kinds: dict[str, int] = field(default_factory=dict)
    series: list[int] = field(default_factory=list)
    streak: int = 0
    last: dict[str, Any] | None = None


async def family_activity(
    database: Database, members: list[UUID], today: datetime, days: int
) -> list[MemberActivity]:
    """``today``: the start of today in the portal's time zone; ``days``: the window (today included)."""
    zone = today.tzinfo
    since = today - timedelta(days=LOOK_BACK_DAYS)
    window = today - timedelta(days=days - 1)
    async with database.session() as session:
        rows = (
            await session.execute(
                select(
                    Activity.user_id,
                    Activity.kind,
                    Activity.started_at,
                    Activity.watched_s,
                    Activity.progress,
                    Activity.title,
                    Activity.parent_title,
                    Activity.object_id,
                ).where(
                    Activity.user_id.in_(members),
                    Activity.counted.is_(True),
                    Activity.started_at >= since,
                )
            )
        ).all()
    out = {user: MemberActivity(user, series=[0] * days) for user in members}
    seconds: dict[UUID, list[float]] = {user: [0.0] * days for user in members}
    kinds: dict[UUID, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    active_days: dict[UUID, set[Any]] = defaultdict(set)
    for user, kind, started, watched, progress, title, parent, object_id in rows:
        if user not in out:
            continue
        member = out[user]
        local = started.astimezone(zone)
        if (watched or 0) >= 60:
            active_days[user].add(local.date())
        if member.last is None or local > member.last["at"]:
            member.last = {"title": parent or title, "kind": kind, "object_id": object_id, "at": local}
        if started < window:
            continue
        index = (local.date() - window.date()).days
        if 0 <= index < days:
            seconds[user][index] += float(watched or 0)
        kinds[user][kind] += float(watched or 0)
        member.plays += 1
        member.finished += int((progress or 0) >= FINISHED)
    for user, member in out.items():
        member.series = [int(s // 60) for s in seconds[user]]
        member.minutes = sum(member.series)
        member.kinds = {
            k: int(v // 60) for k, v in sorted(kinds[user].items(), key=lambda kv: -kv[1]) if v >= 60
        }
        day = today.date()
        if day not in active_days[user]:
            day -= timedelta(days=1)  # today still young: the streak runs to yesterday
        while day in active_days[user]:
            member.streak += 1
            day -= timedelta(days=1)
    return list(out.values())
