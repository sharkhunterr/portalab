"""Reward notifications (T017; FR-033): rewards, level-ups and achievements reach users **only** through the
notification engine (010), after the ledger transaction committed, with coalescing-friendly dedup keys.
A notification failure never affects the reward."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any
from uuid import UUID

from portalab.capabilities.marketplace import GIFTS
from portalab.capabilities.media_core import CONTENT_BOOSTERS
from portalab.capabilities.notifications import NOTIFY, CommunicationRequest, Users
from portalab.capabilities.registry import CapabilityRegistry
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
    "reward": {"reason": "none", "boost": "none"},
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

    async def boosters(self, user: UUID, content: UUID, count: int, reason: str) -> int:
        """Issue 234: a content's boosters a rule gives (the cards') — how many were given; a failure never
        affects the reward."""
        try:
            providers = self.capabilities.system_providers(CONTENT_BOOSTERS)
            if not providers:
                return 0
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
