"""Shell module facade (spec 004): navigation registry, assembler, epochs, diagnostics, observability."""

from portalab.capabilities.events import (
    ConsumerRegistry,
    EventTypeRegistry,
    default_consumers,
    default_event_types,
)
from portalab.capabilities.navigation import NavigationRegistry, default_navigation
from portalab.capabilities.observability import (
    Check,
    CheckResult,
    ObservableRegistry,
    ObservedComponent,
    default_observables,
)
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock
from portalab.modules.shell import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.shell import settings as _settings  # noqa: F401 — declares settings
from portalab.modules.shell.assembler.assembler import NavigationAssembler
from portalab.modules.shell.assembler.epochs import CONSUMER, Epochs, epoch_consumer
from portalab.modules.shell.builtin import register_builtin
from portalab.modules.shell.event_types import register_event_types
from portalab.modules.shell.validator.isolator import Isolator

OWNER = "module:shell"
PROBE = Principal(channel="system")


class ShellModule:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        authorizer: Authorizer,
        capabilities: CapabilityRegistry,
        *,
        registry: NavigationRegistry = default_navigation,
        clock: Clock | None = None,
        event_types: EventTypeRegistry = default_event_types,
        consumers: ConsumerRegistry = default_consumers,
        observables: ObservableRegistry = default_observables,
    ) -> None:
        self.database = database
        self.registry = registry
        self.epochs = Epochs(database, clock=clock)
        self.isolator = Isolator(database, events, clock=clock)
        self.assembler = NavigationAssembler(registry, authorizer, capabilities, self.epochs, clock=clock)
        self.event_types = event_types
        self.consumers = consumers
        self.observables = observables

    def register(self) -> None:
        register_builtin(self.registry)
        register_event_types(self.event_types)
        if self.consumers.get(CONSUMER) is None:
            self.consumers.register(epoch_consumer(lambda: self.epochs))

        async def builds() -> CheckResult:
            view = await self.assembler.build(PROBE)
            if view.get("degraded"):
                return CheckResult("failing", "navigation could not be assembled")
            return CheckResult(
                "ok", "navigation assembles", {"entries": sum(len(g["entries"]) for g in view["groups"])}
            )

        self.observables.declare(
            ObservedComponent(
                "shell", OWNER, label="Navigation", functional_checks=(Check("assembly", builds),), impact=4
            )
        )

    async def flush_diagnostics(self) -> int:
        return await self.isolator.record(
            self.registry.drain_rejections() + self.assembler.drain_runtime_rejections()
        )
