"""Where a member's gains come from (027, the progression page): every positive movement of a value over a
period sorted into sources — what each action gave (plays, requests, shop, support, visits…),
quests, achievements, level rewards, manual grants — and the **bonuses** on top of the actions' own amounts
(play streaks, campaigns, the overall pace, boosts bought in the shop), split from each grant's recorded
modifiers; per day and in all. Own data only."""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import Date, cast, func, or_, select

from portalab.core.db import Database
from portalab.modules.gamification.models import LedgerTransaction, PlayKind, RewardRule

GAINS = ("grant", "manual", "refund", "correction")
QUESTS = {"quest", "daily", "challenge", "discovery"}  # #104: discovery missions are quests too


def is_wheel(source_kind: str, source_ref: str | None) -> bool:
    """Issue 225: a gain or a loss of the daily wheel (its first spins were recorded as « daily »)."""
    return source_kind == "wheel" or (source_ref or "").startswith("wheel:")


ACTIONS = (
    ("media.request", "requests"),  # #129: asking for a title is not playing it
    ("media.radio", "radio"),  # issue 227: the radio listened to, a song asked for
    ("media.leaving", "rescue"),  # issue 228: a title about to be deleted, watched
    ("media.", "media"),
    ("marketplace.", "shop"),
    ("project.", "shop"),
    ("ticket.", "support"),
    ("feedback.", "support"),
    ("user.signed_in", "visits"),
)


# issue 160: a play's gains show by what was played — the kinds the media services report, grouped as members
# think of them; a play of an unknown kind stays « media »
PLAY_SOURCES = {
    "episode": "episode",
    "season": "episode",
    "series": "episode",
    "show": "episode",
    "movie": "movie",
    "live": "live",
    "book": "book",
    "comic": "book",
    "audiobook": "audiobook",
    "track": "music",
    "album": "music",
    "artist": "music",
    "music": "music",
    "game": "game",
}
PLAY_KINDS = ("episode", "movie", "live", "book", "audiobook", "music", "game", "media")


def play_source(kind: str | None) -> str:
    return PLAY_SOURCES.get(kind or "", "media")


def action_of(event_type: str | None, kind: str | None = None) -> str:
    for prefix, source in ACTIONS:
        if event_type and event_type.startswith(prefix):
            return play_source(kind) if source == "media" else source
    return "activity"


def bonus_of(source_ref: str) -> str | None:
    if source_ref.startswith("streak"):
        return "streak"
    if source_ref.startswith("campaign"):
        return "campaigns"
    if source_ref == "pace":
        return "pace"
    if source_ref.startswith("boost"):
        return "boost"  # #55: a boost bought in the shop
    return None  # the rule's own multiplier stays with the action


def factors(modifiers: dict[str, Any]) -> dict[str, float]:
    """Issue 258: each bonus's multiplier in a movement (a streak's 1.5, a boost's 2), as the journal shows
    it."""
    out: dict[str, float] = {}
    for m in (modifiers or {}).get("applied", []):
        source = bonus_of(str(m.get("source_ref", "")))
        factor = float(m.get("factor", 1))
        if source and factor > 1:
            out[source] = out.get(source, 1.0) * factor
    return out


def split(row_kind: str, delta: int, base: int, modifiers: dict[str, Any], action: str) -> dict[str, float]:
    """One movement's amount by source: the action's own part, the bonuses in proportion to their boost —
    an action's, or (issue 226) a quest's, an achievement's or a level's reward boosted the same way."""
    if row_kind != "reward_rule" and not (modifiers or {}).get("applied"):
        return {action: float(delta)}
    own = float(min(max(base, 0), delta)) if base else float(delta)
    out: dict[str, float] = {action: own}
    extra = delta - own
    boosts = [
        (source, float(m.get("factor", 1)) - 1)
        for m in (modifiers or {}).get("applied", [])
        if (source := bonus_of(str(m.get("source_ref", "")))) and float(m.get("factor", 1)) > 1
    ]
    weight = sum(b for _, b in boosts)
    if extra > 0 and weight > 0:
        for source, boost in boosts:
            out[source] = out.get(source, 0.0) + extra * boost / weight
    elif extra > 0:
        out[action] += extra
    return out


async def sources(database: Database, user: UUID, value: str, since: datetime, zone: str) -> dict[str, Any]:
    day = cast(func.timezone(zone, LedgerTransaction.occurred_at), Date)
    async with database.session() as session:
        events = {
            key: event_type
            for key, event_type in (
                await session.execute(select(RewardRule.key, RewardRule.event_type))
            ).all()
        }
        rows = (
            await session.execute(
                select(
                    day,
                    LedgerTransaction.source_kind,
                    LedgerTransaction.rule_key,
                    LedgerTransaction.delta,
                    LedgerTransaction.base_amount,
                    LedgerTransaction.modifiers,
                    PlayKind.kind,
                    LedgerTransaction.source_ref,
                )
                .outerjoin(PlayKind, PlayKind.event_id == LedgerTransaction.trigger_event_id)
                .where(
                    LedgerTransaction.user_id == user,
                    LedgerTransaction.value == value,
                    # a correction takes back part of a gain: counted against the day it is dated
                    or_(LedgerTransaction.delta > 0, LedgerTransaction.kind == "correction"),
                    LedgerTransaction.kind.in_(GAINS),
                    LedgerTransaction.occurred_at >= since,
                )
            )
        ).all()
    per_day: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    totals: dict[str, float] = defaultdict(float)
    for when, kind, rule_key, delta, base, modifiers, played, ref in rows:
        if is_wheel(kind, ref):
            action = "wheel"
        elif kind == "reward_rule":
            action = action_of(events.get(rule_key or ""), played)
        elif kind in QUESTS:
            action = "quests"
        elif kind == "achievement":
            action = "achievements"
        elif kind == "level_reward":
            action = "levels"
        else:
            action = "other"
        for source, amount in split(kind, int(delta), int(base or 0), modifiers or {}, action).items():
            per_day[when.isoformat()][source] += amount
            totals[source] += amount
    ordered = sorted(totals.items(), key=lambda item: -item[1])
    return {
        "value": value,
        "total": round(sum(a for a in totals.values() if a > 0)),
        "sources": [{"source": s, "amount": round(a)} for s, a in ordered if round(a) > 0],
        "days": [
            {"day": d, "amounts": {s: round(a) for s, a in amounts.items() if round(a) > 0}}
            for d, amounts in sorted(per_day.items())
        ],
    }


def since_days(now: datetime, days: int) -> datetime:
    return now - timedelta(days=days)
