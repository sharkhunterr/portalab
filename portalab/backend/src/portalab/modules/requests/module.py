"""Requests module facade (issue 363, #378): the team as a request service — the books, audiobooks, games…
no other service asks for, asked and handled as every request is (the media's: « My requests », the
administrators' queue, quotas, figures). Switched on or off from the module manager like every module;
the kinds of titles it takes set by the administrators (``requests.config``); the library's new titles
close the requests they answer."""

from datetime import timedelta
from typing import Any

from portalab.capabilities.administration import EXTENSION_STATE_CAPABILITY
from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.media import REQUESTS
from portalab.capabilities.record_sink import SinkRegistry, default_sinks
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.registry import JobRegistry
from portalab.core.logging import get_logger
from portalab.core.time import Clock
from portalab.modules.requests import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.requests.service import TEAM, TeamRequests
from portalab.modules.requests.settings import KEY, RequestsConfig, config_of

KEY_MODULE = "requests"
OWNER = "module:requests"
SWEEP_JOB = "requests.sweep"
log = get_logger("portalab.requests")


class RequestsModule:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        *,
        clock: Clock | None = None,
        sinks: SinkRegistry = default_sinks,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.config = RequestsConfig()
        self.team = TeamRequests(database, capabilities, lambda: self.config, sinks, clock=clock)

    def register(self) -> None:
        # the team among the request services: the portal sends it the kinds of titles it takes
        if not any(p.instance_ref == str(TEAM) for p in self.capabilities.system_providers(REQUESTS)):
            self.capabilities.provide(
                REQUESTS, self.team, instance_ref=str(TEAM), owner=OWNER, metadata={"name": "Team"}
            )

    async def enabled(self) -> bool:
        """Switched on in the module manager (every module is, without its toggles)."""
        providers = self.capabilities.system_providers(EXTENSION_STATE_CAPABILITY)
        if not providers:
            return True
        try:
            return bool(await providers[0].provider.enabled("module", KEY_MODULE))
        except Exception:
            return True

    async def refresh_config(self) -> None:
        try:
            providers = self.capabilities.system_providers(CONFIG)
            if providers:
                self.config = config_of((await providers[0].provider.get(KEY)).value)
        except Exception:
            log.warning("requests configuration not refreshed")

    def register_jobs(self, jobs: JobRegistry) -> list[Any]:
        async def sweep() -> None:
            if await self.enabled():
                await self.team.sweep()

        return [
            self.refresh_config,
            # the requests the library's new titles answer, closed every quarter of an hour
            register_periodic(jobs, self.database, SWEEP_JOB, timedelta(minutes=15), sweep, owner=OWNER),
        ]
