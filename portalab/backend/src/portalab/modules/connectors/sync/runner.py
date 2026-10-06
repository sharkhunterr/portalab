"""Sync runner (T023; FR-014..021, US5/US6).

One run per service at a time (PostgreSQL advisory lock held on a dedicated connection): an overlapping
scheduled trigger is skipped, a manual one is refused (``service.sync_in_progress``). Records go to the
``RecordSink`` registered for the capability in batches; a failing batch fails the run without rolling back
the batches already stored. Removals — explicit ``removed`` records and, for a full resync, active records
the source no longer lists — are applied **only** when the whole run succeeded, and a full resync that
would deactivate more than ``resync.confirmDeleteRatio`` of the service's records needs an explicit
confirmation. ``observed_at`` from the source is passed through untouched (never replaced by sync time).
The run is written once to the append-only ``sync_runs`` history when it ends.
"""

import asyncio
import time
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select, text

from portalab.capabilities.connector_sdk import Connector, ServiceHandle, SourceRecord, SyncProgress
from portalab.capabilities.record_sink import (
    RecordSink,
    ServiceRef,
    SinkRegistry,
    SyncDriver,
    default_sinks,
)
from portalab.core.authz_port import Principal
from portalab.core.ids import new_id
from portalab.core.logging import redact_text
from portalab.core.metrics import default_metrics
from portalab.core.time import utc_now
from portalab.modules.connectors.models import Service, ServiceCapability, SyncRun, SyncState
from portalab.modules.connectors.observability import log, metric_part, metrics
from portalab.modules.connectors.services.common import ServiceDisabled, SyncInProgress, publish
from portalab.modules.connectors.services.manager import SYSTEM, ServiceManager

RunKind = Literal["scheduled", "manual", "resync_partial", "resync_full"]
DELETION_CONFIRMATION = "deletion_confirmation_required"


@dataclass
class RunOutcome:
    run_id: UUID
    service_id: UUID
    kind: str
    status: str = "succeeded"
    added: int = 0
    modified: int = 0
    removed: int = 0
    ignored: int = 0
    errored: int = 0
    partial: bool = False
    last_error: str | None = None
    withheld_removals: int = 0
    capabilities: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": str(self.run_id),
            "service_id": str(self.service_id),
            "kind": self.kind,
            "status": self.status,
            "added": self.added,
            "modified": self.modified,
            "removed": self.removed,
            "ignored": self.ignored,
            "errored": self.errored,
            "partial": self.partial,
            "last_error": self.last_error,
            "withheld_removals": self.withheld_removals,
        }


@dataclass(frozen=True, slots=True)
class _Context:
    service: ServiceHandle
    capability: str
    kind: RunKind


def source_ref(row: Service) -> ServiceRef:
    return ServiceRef(service_id=row.id, source_system=f"{row.connector_key}:{row.id}")


class _Failed(Exception):
    def __init__(self, message: str, *, source: bool) -> None:
        super().__init__(message)
        self.source = source  # True: the connector/source failed (counts against the breaker)


class SyncRunner:
    def __init__(self, manager: ServiceManager, sinks: SinkRegistry = default_sinks) -> None:
        self.manager = manager
        self.sinks = sinks

    def _lock_key(self, service_id: UUID) -> str:
        return f"connectors.sync:{service_id}"

    async def run(
        self,
        service_id: UUID,
        *,
        kind: RunKind = "scheduled",
        actor: Principal | None = None,
        capability: str | None = None,
        allow_large_deletion: bool = False,
    ) -> RunOutcome | None:
        """Run one sync; ``None`` when a scheduled run is skipped (overlap, not enabled, circuit open)."""
        async with self.manager.database.engine.connect() as lock:
            locked = await lock.scalar(
                text("SELECT pg_try_advisory_lock(hashtextextended(:key, 0))"),
                {"key": self._lock_key(service_id)},
            )
            await lock.commit()
            if not locked:
                metrics.increment("connectors.sync.overlap_skipped")
                if kind == "scheduled":
                    return None
                raise SyncInProgress("A synchronization of this service is already running.")
            try:
                return await self._run_locked(service_id, kind, actor, capability, allow_large_deletion)
            finally:
                await lock.execute(
                    text("SELECT pg_advisory_unlock(hashtextextended(:key, 0))"),
                    {"key": self._lock_key(service_id)},
                )
                await lock.commit()

    async def _run_locked(
        self,
        service_id: UUID,
        kind: RunKind,
        actor: Principal | None,
        only: str | None,
        allow_large_deletion: bool,
    ) -> RunOutcome | None:
        manager = self.manager
        async with manager.database.session() as session:
            row = await manager._row(session, service_id)
            caps = {
                c.capability: c
                for c in (
                    await session.execute(
                        select(ServiceCapability).where(ServiceCapability.service_id == service_id)
                    )
                ).scalars()
            }
            state = await session.get(SyncState, service_id)
            cursors: dict[str, Any] = dict(state.cursor or {}) if state else {}
        runnable = row.state in ("enabled", "error", "unavailable")
        breaker = manager.breakers.get(str(service_id))
        if not runnable or (kind == "scheduled" and not breaker.allow()):
            if kind == "scheduled":
                return None
            raise ServiceDisabled("This service is not enabled; it cannot be synchronized.")
        connector = manager.connector(row.connector_key)
        handle = manager.handle(row)
        ref = source_ref(row)
        outcome = RunOutcome(run_id=new_id(), service_id=service_id, kind=kind)
        started = utc_now(manager.clock)
        clock_start = time.monotonic()
        async with manager.database.unit_of_work() as uow:
            sync_state = await uow.session.get(SyncState, service_id, with_for_update=True)
            if sync_state is None:
                sync_state = SyncState(service_id=service_id, consecutive_failures=0)
                uow.session.add(sync_state)
            sync_state.status, sync_state.last_attempt_at = "running", started
            await publish(
                manager.events,
                uow.session,
                "sync.started",
                {"service_id": str(service_id), "run_id": str(outcome.run_id), "kind": kind},
                service_id=service_id,
                actor=actor or SYSTEM,
                occurred_at=started,
            )
        source_failed = False
        full = kind == "resync_full"
        fresh = kind in ("resync_partial", "resync_full")
        for binding in connector.provides:
            name = binding.spec.name
            if not (binding.syncable or binding.driven) or (only and name != only):
                continue
            cap = caps.get(name)
            if cap is None or not cap.enabled:
                continue
            if binding.driven:
                driver = self.sinks.driver(name)
                if driver is None:
                    continue
                outcome.capabilities.append(name)
                try:
                    await self._drive(driver, ref, name, kind, outcome)
                except _Failed as exc:
                    outcome.status = "failed"
                    outcome.last_error = redact_text(str(exc))[:1000]
                    source_failed = exc.source
                    break
                continue
            sink = self.sinks.get(name)
            if sink is None:
                log.info("no sink for capability", extra={"fields": {"capability": name}})
                continue
            outcome.capabilities.append(name)
            try:
                await self._sync_capability(
                    connector,
                    handle,
                    sink,
                    ref,
                    name,
                    kind,
                    None if fresh else cursors.get(name),
                    outcome,
                    full,
                    allow_large_deletion,
                )
            except _Failed as exc:
                outcome.status = "failed"
                outcome.last_error = redact_text(str(exc))[:1000]
                source_failed = exc.source
                break
        if outcome.status != "failed" and outcome.partial:
            outcome.status = "partial"
        if source_failed:
            await breaker.record_failure()
        elif outcome.status != "failed":
            await breaker.record_success()
        await self._finish(row, outcome, started, actor)
        metrics.gauge(
            f"connectors.sync.duration_seconds.{metric_part(str(service_id))}", time.monotonic() - clock_start
        )
        default_metrics.histogram(
            "connectors",
            "sync.duration",
            (time.monotonic() - clock_start) * 1000,
            {"service": str(service_id)},
        )
        metrics.increment(f"connectors.sync.{outcome.status}")
        return outcome

    async def _sync_capability(
        self,
        connector: Connector,
        handle: ServiceHandle,
        sink: RecordSink,
        ref: ServiceRef,
        capability: str,
        kind: RunKind,
        cursor: Mapping[str, Any] | None,
        outcome: RunOutcome,
        full: bool,
        allow_large_deletion: bool,
    ) -> None:
        batch: list[SourceRecord] = []
        removed: list[str] = []
        seen: set[str] = set()
        size = self.manager.config.sync_batch_size
        step = self.manager.config.http_timeout_seconds * 3
        total: int | None = None
        await self._progress(ref.service_id, capability, 0, None)

        async def flush() -> None:
            if not batch:
                return
            try:
                result = await sink.upsert(list(batch), ref)
            except Exception as exc:
                outcome.errored += len(batch)
                raise _Failed(
                    f"the {capability} sink rejected a batch ({type(exc).__name__})", source=False
                ) from exc
            outcome.added += result.added
            outcome.modified += result.modified
            outcome.ignored += result.ignored
            outcome.errored += result.errored
            batch.clear()
            await self._progress(ref.service_id, capability, len(seen), total)

        iterator: AsyncIterator[SourceRecord | SyncProgress] = connector.sync(
            _Context(handle, capability, kind), cursor
        ).__aiter__()
        while True:
            try:
                item = await asyncio.wait_for(anext(iterator), timeout=step)
            except StopAsyncIteration:
                break
            except TimeoutError as exc:
                raise _Failed("the service did not answer in time", source=True) from exc
            except Exception as exc:
                raise _Failed(f"the service sync failed ({type(exc).__name__}: {exc})", source=True) from exc
            if isinstance(item, SyncProgress):
                if item.total is not None:
                    total = item.total
                await flush()
                if item.cursor:  # an empty cursor only reports progress
                    await self._checkpoint(ref.service_id, capability, dict(item.cursor))
                else:
                    await self._progress(ref.service_id, capability, len(seen), total)
                continue
            if not isinstance(item, SourceRecord) or not item.external_id:
                outcome.errored += 1
                continue
            seen.add(item.external_id)
            if item.removed:
                removed.append(item.external_id)
                continue
            batch.append(item)
            if len(batch) >= size:
                await flush()
        await flush()
        doomed = list(dict.fromkeys(removed))
        if full:
            active = await sink.active_ids(ref)
            missing = sorted(active - seen)
            ratio = len(missing) / len(active) if active else 0.0
            if (
                missing
                and ratio > self.manager.config.resync_confirm_delete_ratio
                and not allow_large_deletion
            ):
                outcome.partial = True
                outcome.withheld_removals += len(missing)
                outcome.last_error = DELETION_CONFIRMATION
            else:
                doomed.extend(m for m in missing if m not in doomed)
        if doomed:
            outcome.removed += await sink.deactivate(doomed, ref)

    async def _drive(
        self, driver: SyncDriver, ref: ServiceRef, capability: str, kind: RunKind, outcome: RunOutcome
    ) -> None:
        """027: a capability the consuming module pulls itself (history, metadata), with its progress."""
        await self._progress(ref.service_id, capability, 0, None)

        async def report(done: int, total: int | None) -> None:
            await self._progress(ref.service_id, capability, done, total)

        try:
            result = await driver.drive(ref, kind, report)
        except Exception as exc:
            raise _Failed(f"the {capability} sync failed ({type(exc).__name__}: {exc})", source=True) from exc
        outcome.added += result.added
        outcome.modified += result.modified
        outcome.ignored += result.ignored
        outcome.errored += result.errored

    async def _progress(self, service_id: UUID, capability: str, done: int, total: int | None) -> None:
        """027: how far the running sync got, for the live progress bar of the services page."""
        async with self.manager.database.unit_of_work() as uow:
            state = await uow.session.get(SyncState, service_id, with_for_update=True)
            if state is not None:
                started = (state.progress or {}).get("started_at") or utc_now(self.manager.clock).isoformat()
                state.progress = {
                    "capability": capability,
                    "done": done,
                    "total": max(total, done) if total is not None else None,
                    "started_at": started,
                }

    async def _checkpoint(self, service_id: UUID, capability: str, cursor: dict[str, Any]) -> None:
        async with self.manager.database.unit_of_work() as uow:
            state = await uow.session.get(SyncState, service_id, with_for_update=True)
            if state is not None:
                state.cursor = {**(state.cursor or {}), capability: cursor}

    async def _finish(self, row: Service, outcome: RunOutcome, started: Any, actor: Principal | None) -> None:
        manager = self.manager
        finished = utc_now(manager.clock)
        interval = row.sync_interval_seconds or manager.config.default_sync_interval_seconds
        async with manager.database.unit_of_work() as uow:
            uow.session.add(
                SyncRun(
                    id=outcome.run_id,
                    service_id=row.id,
                    capability=outcome.capabilities[0] if len(outcome.capabilities) == 1 else None,
                    kind=outcome.kind,
                    triggered_by=actor.user_id if actor else None,
                    started_at=started,
                    finished_at=finished,
                    status=outcome.status,
                    added=outcome.added,
                    modified=outcome.modified,
                    removed=outcome.removed,
                    ignored=outcome.ignored,
                    errored=outcome.errored,
                    last_error=outcome.last_error,
                    partial=outcome.partial,
                )
            )
            state = await uow.session.get(SyncState, row.id, with_for_update=True)
            if state is not None:
                failed = outcome.status == "failed"
                state.status = "failed" if failed else "idle"
                state.progress = None
                state.consecutive_failures = state.consecutive_failures + 1 if failed else 0
                if not failed:
                    state.last_success_at = finished
                state.next_run_at = finished + timedelta(seconds=interval)
            await publish(
                manager.events,
                uow.session,
                "sync.failed" if outcome.status == "failed" else "sync.completed",
                {
                    "service_id": str(row.id),
                    "run_id": str(outcome.run_id),
                    "kind": outcome.kind,
                    "status": outcome.status,
                    "added": outcome.added,
                    "modified": outcome.modified,
                    "removed": outcome.removed,
                    "ignored": outcome.ignored,
                    "errored": outcome.errored,
                },
                service_id=row.id,
                actor=actor or SYSTEM,
                occurred_at=finished,
            )
