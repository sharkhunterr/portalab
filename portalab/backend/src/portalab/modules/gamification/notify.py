"""Reward notifications (T017; FR-033): rewards, level-ups and achievements reach users **only** through the
notification engine (010), after the ledger transaction committed, with coalescing-friendly dedup keys.
A notification failure never affects the reward."""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any
from uuid import UUID

from portalab.capabilities.marketplace import GIFTS
from portalab.capabilities.media_core import CATALOG, CONTENT_BOOSTERS
from portalab.capabilities.notifications import NOTIFY, CommunicationRequest, Users
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.modules.gamification.observability import log

CATEGORIES = (
    "gamification.reward",
    "gamification.level_up",
    "gamification.achievement",
    "gamification.quest",
)
# issue 258: a series of the same gain (the radio's quarters of an hour, episodes one after the other) merges
# into one notification while it is unread, up to this long after the last
SERIES_S = 3600
REWARD_VALUES = ("xp", "coins", "contribution")


DEFAULTS: dict[str, dict[str, Any]] = {
    # issue 261: the work a gain was about, the minutes its rule counted, a streak's multiplier
    "reward": {"reason": "none", "boost": "none", "work": "none", "minutes": 0, "streak": 0},
    "quest": {"xp": 0, "coins": 0, "contribution": 0},
    "achievement": {"xp": 0, "coins": 0, "contribution": 0},
}


@dataclass(frozen=True, slots=True)
class Note:
    kind: str  # reward | level_up | achievement
    user: UUID
    dedup: str
    params: Mapping[str, Any] = field(default_factory=dict)
    gifts: tuple[str, ...] = ()  # 027: shop products the achievement gives, offered once committed


class Notifier:
    def __init__(self, capabilities: CapabilityRegistry) -> None:
        self.capabilities = capabilities

    async def send(self, notes: Iterable[Note]) -> None:
        notes = together(list(notes))
        await self._gift(notes)
        try:
            providers = self.capabilities.system_providers(NOTIFY)
        except Exception:
            return
        if not providers:
            return
        for note in notes:
            note = await self._work(note)
            try:
                await providers[0].provider.send(
                    CommunicationRequest(
                        category=f"gamification.{note.kind}",
                        template_key=f"gamification:notify.{note.kind}",
                        audience=Users((note.user,)),
                        dedup_key=note.dedup,
                        # issue 186: every parameter its message names is there (« none » when it has none)
                        params={**DEFAULTS.get(note.kind, {}), **dict(note.params)},
                        # issue 258: a rule's gains merge with each other (a series), not with others'
                        subject_ref=_subject(note),
                        action_url="/progression",
                    )
                )
            except Exception:
                log.warning("reward notification not sent", extra={"fields": {"kind": note.kind}})

    async def _work(self, note: Note) -> Note:
        """Issue 261: the work a gain was about (« Sissi · S2 E6 », « Dune (2021) »), as the member may see it
        in the catalog — its object in place of its name; a failure leaves it unsaid."""
        raw = note.params.get("object")
        if note.kind != "reward" or not raw:
            return note
        params = {key: value for key, value in note.params.items() if key != "object"}
        try:
            catalog = self.capabilities.system_providers(CATALOG)
            work = (
                await catalog[0].provider.get(UUID(str(raw)), Principal(user_id=note.user))
                if catalog
                else None
            )
        except Exception:
            work = None
        if work is not None:
            params["work"] = work_name(work)[:160]
        return replace(note, params=params)

    async def boosters(
        self, user: UUID, content: UUID | None, count: int, reason: str, among: dict[str, Any] | None = None
    ) -> int:
        """Issue 234: a content's boosters a rule gives (the cards') — issue 356: or the works its event names
        (a genre, a year) when it is about no content; how many were given; a failure never affects the
        reward."""
        try:
            providers = self.capabilities.system_providers(CONTENT_BOOSTERS)
            if not providers:
                return 0
            if content is None:
                return int(await providers[0].provider.give_among(user, among or {}, count, reason[:200]))
            return int(await providers[0].provider.give(user, content, count, reason[:200]))
        except Exception:
            log.warning("content booster not given", extra={"fields": {"content": str(content)}})
            return 0

    async def _gift(self, notes: list[Note]) -> None:
        """027: what an unlocked achievement gives (badge, title, frame…) — never twice (a product owned
        already is skipped by the shop); a failure never affects the achievement."""
        wanted = [(note.user, product, note.dedup) for note in notes for product in note.gifts]
        if not wanted:
            return
        try:
            providers = self.capabilities.system_providers(GIFTS)
        except Exception:
            return
        if not providers:
            return
        for user, product, reason in wanted:
            try:
                await providers[0].provider.gift(user, product, reason[:200])
            except Exception:
                log.warning("achievement gift not offered", extra={"fields": {"product": product}})


def _subject(note: Note) -> str:
    rule = note.params.get("rule") if note.kind == "reward" else None
    return f"progression:{note.user}:{rule}" if rule else f"progression:{note.user}"


def together(notes: list[Note]) -> list[Note]:
    """Issue 258: one gain, one notification — the XP, the site's currency and the contribution one rule gave
    a member at once are told together (their amounts by value), in the place of the first."""
    out: list[Note] = []
    first: dict[tuple[UUID, str], int] = {}
    for note in notes:
        value = note.params.get("value")
        if note.kind != "reward" or value not in REWARD_VALUES or not note.params.get("rule"):
            out.append(note)
            continue
        key = (note.user, str(note.params["rule"]))
        if key not in first:
            first[key] = len(out)
            out.append(replace(note, params={**note.params, str(value): note.params.get("amount", 0)}))
            continue
        kept = out[first[key]]
        out[first[key]] = replace(kept, params={**kept.params, str(value): note.params.get("amount", 0)})
    return out


def work_name(work: Any) -> str:
    """An episode by its series, season and number (and its own title when it says more than its number), a
    film by its year."""
    if work.kind == "episode" and work.series:
        season, number = ("?" if n is None else n for n in (work.season, work.number))
        at = f"S{season} E{number}"
        own = "" if re.fullmatch(r"(?i)[ée]pisode \d+", work.title or "") else f" · {work.title}"
        return f"{work.series} · {at}{own}"
    return f"{work.title} ({work.year})" if work.year else str(work.title)
