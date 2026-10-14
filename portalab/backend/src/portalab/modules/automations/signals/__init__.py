"""Issue 122: the service signals watched for automations — read each minute while an active automation
listens to ``service.signal_changed``; a value that changed (or a first « true ») is published once."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.health import SERVICE_DIRECTORY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.service_signals import Signal, SignalRegistry, Value, default_signals
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.automations.events import SIGNAL_CHANGED
from portalab.modules.automations.models import SignalValue
from portalab.modules.automations.observability import log

READ_SECONDS = 20.0


class SignalWatcher:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        capabilities: CapabilityRegistry,
        listened: Callable[[], Awaitable[bool]],
        *,
        registry: SignalRegistry = default_signals,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.capabilities = capabilities
        self.listened = listened  # whether an active automation reacts to the signals
        self.registry = registry
        self.clock = clock

    def services(self, signal: Signal) -> list[tuple[str, Any]]:
        return [
            (str(r.instance_ref), r.provider)
            for r in self.capabilities.system_providers(signal.capability)
            if r.instance_ref is not None
        ]

    async def current(self) -> list[dict[str, Any]]:
        """Every signal of every service as it stands now (the editor shows them while one is built)."""
        out = []
        names = await self._names()
        for signal in self.registry.all():
            for service_id, provider in self.services(signal):
                out.append(
                    {
                        "signal": signal.key,
                        "label": signal.label,
                        "description": signal.description,
                        "kind": signal.kind,
                        "service_id": service_id,
                        "service_label": names.get(service_id),
                        "value": await self._read(signal, service_id, provider),
                    }
                )
        return out

    async def run(self) -> int:
        if not await self.listened():
            return 0
        names: dict[str, str] | None = None
        published = 0
        for signal in self.registry.all():
            for service_id, provider in self.services(signal):
                value = await self._read(signal, service_id, provider)
                if value is None:
                    continue  # unknown now: never a change
                changed, previous, first = await self._store(service_id, signal.key, value)
                if not changed or (first and value is not True):
                    continue  # a first sight tells nothing changed — but a « true » is news
                if names is None:
                    names = await self._names()
                await self._publish(signal, service_id, names.get(service_id), value, previous)
                published += 1
        return published

    async def _read(self, signal: Signal, service_id: str, provider: Any) -> Value | None:
        try:
            return await asyncio.wait_for(signal.read(service_id, provider), READ_SECONDS)
        except Exception as exc:
            log.warning(
                "service signal not read",
                extra={"fields": {"signal": signal.key, "error": type(exc).__name__}},
            )
            return None

    async def _store(self, service_id: str, key: str, value: Value) -> tuple[bool, Value | None, bool]:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(SignalValue, (service_id, key), with_for_update=True)
            if row is None:
                await uow.session.execute(
                    insert(SignalValue)
                    .values(service_id=service_id, signal=key, value=value, seen_at=now, changed_at=now)
                    .on_conflict_do_nothing()
                )
                return True, None, True
            previous = row.value
            row.seen_at = now
            if previous == value and type(previous) is type(value):
                return False, previous, False
            row.value, row.changed_at = value, now
            return True, previous, False

    async def _publish(
        self, signal: Signal, service_id: str, name: str | None, value: Value, previous: Value | None
    ) -> None:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            await self.events.publish(
                uow.session,
                SIGNAL_CHANGED,
                {
                    "service_id": service_id,
                    "service_label": name or service_id,
                    "signal": signal.key,
                    "label": signal.label or None,
                    "value": value,
                    "previous": previous,
                },
                occurred_at=now,
                subject=SubjectRef("service", service_id),
                dedup_key=f"{SIGNAL_CHANGED}:{service_id}:{signal.key}:{now.isoformat()}",
            )

    async def _names(self) -> dict[str, str]:
        providers = self.capabilities.system_providers(SERVICE_DIRECTORY)
        if not providers:
            return {}
        try:
            return {s.id: s.name for s in await providers[0].provider.services()}
        except Exception:
            return {}
