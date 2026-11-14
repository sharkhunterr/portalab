"""Retro module facade (issues 419-421): a game library's games played in the portal's own page, with the
library's emulator (RomM's EmulatorJS) — the game, its firmware and the emulator relayed from the library,
the sittings counted in the portal (statistics, XP, a household profile's screen time) and told to the
library. Switched on or off from the module manager like every module."""

from datetime import timedelta
from typing import Any

from portalab.capabilities.administration import EXTENSION_STATE_CAPABILITY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.registry import JobRegistry
from portalab.core.secrets import SecretBox
from portalab.core.time import Clock
from portalab.modules.retro import permissions as _permissions  # noqa: F401 — declares its permissions
from portalab.modules.retro.accounts import AccountService
from portalab.modules.retro.saves import SaveService
from portalab.modules.retro.service import RetroService

KEY = "retro"
OWNER = "module:retro"
SWEEP_JOB = "retro.sweep"


class RetroModule:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        *,
        clock: Clock | None = None,
        events: EventPublisher | None = None,
        secret_box: SecretBox | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.service = RetroService(database, capabilities, clock=clock, events=events)
        self.saves = SaveService(database, capabilities, self.service, clock=clock)  # 420
        # 426: each member's own account in the libraries (tokens kept encrypted)
        self.accounts = AccountService(database, capabilities, self.service, secret_box, clock=clock)
        self.service.accounts = self.accounts

    def register(self) -> None:
        """Nothing to provide: the module plays what the libraries (``media.retro_source``) and the catalog
        (``media.game_source``) give it."""

    def register_jobs(self, jobs: JobRegistry) -> list[Any]:
        async def sweep() -> None:
            while await self.service.sweep():
                pass
            await self.saves.sync()  # 420: the saves the library did not take yet

        # the sittings whose page went away without a word end, every five minutes
        return [register_periodic(jobs, self.database, SWEEP_JOB, timedelta(minutes=5), sweep, owner=OWNER)]

    async def enabled(self) -> bool:
        """Switched on in the module manager (every module is, without its toggles)."""
        providers = self.capabilities.system_providers(EXTENSION_STATE_CAPABILITY)
        if not providers:
            return True
        try:
            return bool(await providers[0].provider.enabled("module", KEY))
        except Exception:
            return True
