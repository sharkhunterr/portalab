"""Requests module facade (issue 363): the members ask the administrators for a title no service asks for — a
book, an audiobook, a game… —, the others say « me too »; the administrators take them in hand
(``requests.manage``); the library's new titles close the requests they answer. Switched on or off from the
module manager like every module; set up by the administrators (``requests.config``)."""

from datetime import timedelta
from typing import Any

from portalab.capabilities.administration import EXTENSION_STATE_CAPABILITY
from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.events import EventTypeRegistry, default_event_types
from portalab.capabilities.notifications import declare_category, default_categories
from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY, EXPORT_CAPABILITY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.registry import JobRegistry
from portalab.core.logging import get_logger
from portalab.core.time import Clock
from portalab.modules.requests import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.requests.events import register_event_types
from portalab.modules.requests.notify import QUEUE, UPDATES
from portalab.modules.requests.participant import RequestsParticipant
from portalab.modules.requests.service import Requests
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
        events: EventPublisher | None = None,
        event_types: EventTypeRegistry = default_event_types,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.event_types = event_types
        self.config = RequestsConfig()
        self.requests = Requests(database, capabilities, lambda: self.config, events=events, clock=clock)

    def register(self) -> None:
        register_event_types(self.event_types)
        for key, label in (
            (UPDATES, "media:ask.category.updates"),
            (QUEUE, "media:ask.category.queue"),
        ):
            if default_categories.get(key) is None:
                declare_category(key, OWNER, label)
        participant = RequestsParticipant(self.requests)
        for capability in (ERASURE_CAPABILITY, EXPORT_CAPABILITY):
            if not any(p.instance_ref == KEY_MODULE for p in self.capabilities.system_providers(capability)):
                self.capabilities.provide(capability, participant, instance_ref=KEY_MODULE, owner=OWNER)

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
                await self.requests.sweep()

        return [
            self.refresh_config,
            # the requests the library's new titles answer, closed every quarter of an hour
            register_periodic(jobs, self.database, SWEEP_JOB, timedelta(minutes=15), sweep, owner=OWNER),
        ]
