"""Reward notifications (T017; FR-033): rewards, level-ups and achievements reach users **only** through the
notification engine (010), after the ledger transaction committed, with coalescing-friendly dedup keys.
A notification failure never affects the reward."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from portalab.capabilities.marketplace import GIFTS
from portalab.capabilities.notifications import NOTIFY, CommunicationRequest, Users
from portalab.capabilities.registry import CapabilityRegistry
from portalab.modules.gamification.observability import log

CATEGORIES = (
    "gamification.reward",
    "gamification.level_up",
    "gamification.achievement",
    "gamification.quest",
)


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
        notes = list(notes)
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
                        subject_ref=f"progression:{note.user}",
                        action_url="/progression",
                    )
                )
            except Exception:
                log.warning("reward notification not sent", extra={"fields": {"kind": note.kind}})

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
