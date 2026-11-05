"""Games module facade (issue 265): a page of games drawn from the household's library — question after
question alone or in a party, the day's title to find, the memory of one's own cards, the week's retro
challenge, the month's media bingo (issue 356) — set up by the administrators (``games.config``), rewarded by
the reward rules (``games.played``, ``games.challenge_completed``, ``games.bingo_line|card``)."""

from datetime import timedelta
from typing import Any

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.events import EventTypeRegistry, default_event_types
from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY, EXPORT_CAPABILITY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.registry import JobRegistry
from portalab.core.logging import get_logger
from portalab.core.time import Clock
from portalab.modules.games import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.games.bingo import Bingo
from portalab.modules.games.boards import Boards
from portalab.modules.games.challenge import Challenges
from portalab.modules.games.cinemot import Cinemot
from portalab.modules.games.common import Shared
from portalab.modules.games.events import register_event_types
from portalab.modules.games.participant import GamesParticipant
from portalab.modules.games.party import Parties
from portalab.modules.games.pool import Pool
from portalab.modules.games.settings import KEY, GamesConfig, config_of
from portalab.modules.games.solo import Solo

OWNER = "module:games"
CHALLENGE_JOB = "games.challenge"
BINGO_JOB = "games.bingo"
SWEEP_JOB = "games.sweep"
BOARDS_JOB = "games.boards"
log = get_logger("portalab.games")


class GamesModule:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        *,
        clock: Clock | None = None,
        events: EventPublisher | None = None,
        event_types: EventTypeRegistry = default_event_types,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.event_types = event_types
        self.config = GamesConfig()
        self.shared = Shared(capabilities, lambda: self.config, events)
        self.pool = Pool(capabilities, clock=clock)
        self.solo = Solo(database, self.pool, self.shared, clock=clock)
        self.cinemot = Cinemot(database, self.pool, self.shared, clock=clock)
        self.challenges = Challenges(database, self.shared, clock=clock)
        self.bingo = Bingo(database, self.shared, clock=clock)  # issue 356: the month's media bingo
        self.parties = Parties(database, self.pool, self.shared, clock=clock)
        self.boards = Boards(database, self.shared, clock=clock)

    def register(self) -> None:
        register_event_types(self.event_types)
        participant = GamesParticipant(self.database)
        for capability in (ERASURE_CAPABILITY, EXPORT_CAPABILITY):
            if not any(p.instance_ref == "games" for p in self.capabilities.system_providers(capability)):
                self.capabilities.provide(capability, participant, instance_ref="games", owner=OWNER)

    async def refresh_config(self) -> None:
        try:
            providers = self.capabilities.system_providers(CONFIG)
            if providers:
                self.config = config_of((await providers[0].provider.get(KEY)).value)
        except Exception:
            log.warning("games configuration not refreshed")

    def register_jobs(self, jobs: JobRegistry) -> list[Any]:
        async def challenge() -> None:
            await self.challenges.check()

        async def bingo() -> None:
            await self.bingo.check()

        async def sweep() -> None:
            await self.parties.sweep()

        async def boards() -> None:
            await self.boards.close()

        return [
            self.refresh_config,
            # who completed the week's challenge (their play sessions), every half hour
            register_periodic(
                jobs, self.database, CHALLENGE_JOB, timedelta(minutes=30), challenge, owner=OWNER
            ),
            # issue 356: who completed a line or the card of the month's bingo, every half hour
            register_periodic(jobs, self.database, BINGO_JOB, timedelta(minutes=30), bingo, owner=OWNER),
            # parties left open without a move close, every hour
            register_periodic(jobs, self.database, SWEEP_JOB, timedelta(hours=1), sweep, owner=OWNER),
            # a week or a month over: each member placed on a board told their place, every hour
            register_periodic(jobs, self.database, BOARDS_JOB, timedelta(hours=1), boards, owner=OWNER),
        ]
