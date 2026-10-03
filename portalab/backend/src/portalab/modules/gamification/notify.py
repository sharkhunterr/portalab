"""Reward notifications (T017; FR-033): rewards, level-ups and achievements reach users **only** through the
notification engine (010), after the ledger transaction committed, with coalescing-friendly dedup keys.
A notification failure never affects the reward."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from portalab.capabilities.notifications import NOTIFY, CommunicationRequest, Users
from portalab.capabilities.registry import CapabilityRegistry
from portalab.modules.gamification.observability import log

CATEGORIES = (
    "gamification.reward",
    "gamification.level_up",
    "gamification.achievement",
    "gamification.quest",
)


@dataclass(frozen=True, slots=True)
class Note:
    kind: str  # reward | level_up | achievement
    user: UUID
    dedup: str
    params: Mapping[str, Any] = field(default_factory=dict)


class Notifier:
    def __init__(self, capabilities: CapabilityRegistry) -> None:
        self.capabilities = capabilities

    async def send(self, notes: Iterable[Note]) -> None:
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
                        params=dict(note.params),
                        subject_ref=f"progression:{note.user}",
                        action_url="/progression",
                    )
                )
            except Exception:
                log.warning("reward notification not sent", extra={"fields": {"kind": note.kind}})
