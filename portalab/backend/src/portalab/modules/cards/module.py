"""Cards module facade (issue 229): the media trading cards — made in advance from the works present, given in
packs when a work is watched to the end, collected per set and per person."""

from datetime import timedelta
from typing import Any

from portalab.capabilities.events import ConsumerRegistry, default_consumers
from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY, EXPORT_CAPABILITY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.registry import JobRegistry
from portalab.core.logging import get_logger
from portalab.core.time import Clock
from portalab.modules.cards import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.cards.generator import CardForge
from portalab.modules.cards.packs import CONSUMER, Packs
from portalab.modules.cards.participant import CardsParticipant
from portalab.modules.cards.roles import RoleArt
from portalab.modules.cards.service import CardService

OWNER = "module:cards"
SYNC_JOB = "cards.sync"
ROLES_JOB = "cards.role_art"
log = get_logger("portalab.cards")


class CardsModule:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        *,
        clock: Clock | None = None,
        consumers: ConsumerRegistry = default_consumers,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.clock = clock
        self.consumers = consumers
        self.forge = CardForge(database, capabilities, clock=clock)
        self.packs = Packs(database, capabilities, clock=clock)
        self.service = CardService(database)
        self.roles = RoleArt(database, capabilities, clock=clock)

    def register(self) -> None:
        participant = CardsParticipant(self.database)
        for capability in (ERASURE_CAPABILITY, EXPORT_CAPABILITY):
            if not any(p.instance_ref == "cards" for p in self.capabilities.system_providers(capability)):
                self.capabilities.provide(capability, participant, instance_ref="cards", owner=OWNER)
        if self.consumers.get(CONSUMER) is None:
            self.consumers.register(self.packs.consumer())

    def register_jobs(self, jobs: JobRegistry) -> list[Any]:
        async def sync() -> None:
            report = await self.forge.sync()
            if report.made or report.gone:
                log.info("cards made again", extra={"fields": {"made": report.made, "gone": report.gone}})

        async def roles() -> None:
            await self.roles.run()

        return [
            # the works that changed are made again (their fingerprint), every half hour
            register_periodic(jobs, self.database, SYNC_JOB, timedelta(minutes=30), sync, owner=OWNER),
            # the actors' characters, a few people every five minutes (the rarest cards first)
            register_periodic(jobs, self.database, ROLES_JOB, timedelta(minutes=5), roles, owner=OWNER),
        ]
