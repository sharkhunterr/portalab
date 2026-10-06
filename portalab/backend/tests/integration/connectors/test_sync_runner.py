"""005 T020 — sync runs are recorded with counts; duplicates/late records are idempotent; a sink failure
fails the run without rolling back earlier batches; overlapping triggers are skipped; ``observed_at`` is
the source's time, never the sync time."""

import asyncio
from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import select, text

from portalab.capabilities.connector_sdk import CapabilityBinding
from portalab.capabilities.record_sink import Report, ServiceRef, SinkResult
from portalab.connectors.fake import EPOCH, SPEC
from portalab.modules.connectors.models import SyncRun, SyncState
from portalab.modules.connectors.services.common import SyncInProgress
from portalab.modules.connectors.sync.runner import source_ref
from tests.connectors_fixtures import ConnectorsHarness


async def _ref(cn: ConnectorsHarness, service_id: object) -> object:
    async with cn.full.database.session() as session:
        return source_ref(await cn.module.manager._row(session, service_id))  # type: ignore[arg-type]


async def test_run_recorded_with_counts_and_cursor(cn: ConnectorsHarness) -> None:
    service_id = await cn.enabled()
    cn.remote.put("a", at=1, title="A")
    cn.remote.put("b", at=2, title="B")
    first = await cn.module.runner.run(service_id, kind="manual", actor=cn.admin)
    assert first is not None and (first.status, first.added, first.modified) == ("succeeded", 2, 0)
    cn.remote.put("b", at=3, title="B2")
    second = await cn.module.runner.run(service_id)
    assert second is not None and (second.added, second.modified, second.ignored) == (0, 1, 0)  # cursor
    async with cn.full.database.session() as session:
        runs = (await session.execute(select(SyncRun).order_by(SyncRun.started_at))).scalars().all()
        state = await session.get(SyncState, service_id)
    assert [(r.kind, r.status, r.added) for r in runs] == [
        ("manual", "succeeded", 2),
        ("scheduled", "succeeded", 0),
    ]
    assert state is not None and state.cursor == {"demo.items": {"at": 3}} and state.status == "idle"
    assert state.last_success_at is not None and state.next_run_at is not None
    events = await cn.outbox("sync.")
    assert [e["type"] for e in events] == ["sync.started", "sync.completed", "sync.started", "sync.completed"]


async def test_observed_at_is_source_time(cn: ConnectorsHarness) -> None:
    service_id = await cn.enabled()
    cn.remote.put("a", at=42)
    await cn.module.runner.run(service_id, kind="manual")
    row = cn.sink.stored(await _ref(cn, service_id))["a"]  # type: ignore[arg-type]
    assert row.observed_at == EPOCH + timedelta(minutes=42)


async def test_duplicates_and_late_records_are_idempotent(cn: ConnectorsHarness) -> None:
    service_id = await cn.enabled()
    cn.remote.put("a", at=5, title="new")
    await cn.module.runner.run(service_id, kind="manual")
    again = await cn.module.runner.run(service_id, kind="resync_partial")  # re-reads everything
    assert again is not None and (again.added, again.modified, again.ignored) == (0, 0, 1)
    cn.remote.put("a", at=1, title="old")  # a late, older observation
    late = await cn.module.runner.run(service_id, kind="resync_partial")
    assert late is not None and late.ignored == 1
    assert cn.sink.stored(await _ref(cn, service_id))["a"].payload == {"title": "new"}  # type: ignore[arg-type]


async def test_sink_failure_keeps_earlier_batches(cn: ConnectorsHarness) -> None:
    cn.module.config = replace(cn.module.config, sync_batch_size=2)
    service_id = await cn.enabled()
    for index in range(5):
        cn.remote.put(f"i{index}", at=index + 1)
    cn.sink.fail_on = {"i3"}
    outcome = await cn.module.runner.run(service_id, kind="manual")
    assert outcome is not None and outcome.status == "failed" and outcome.added == 2 and outcome.errored == 2
    assert set(cn.sink.stored(await _ref(cn, service_id))) == {"i0", "i1"}  # type: ignore[arg-type]
    assert outcome.last_error is not None and "sink" in outcome.last_error
    async with cn.full.database.session() as session:
        state = await session.get(SyncState, service_id)
    assert state is not None and state.status == "failed" and state.consecutive_failures == 1
    assert (await cn.module.manager.get(service_id)).state == "enabled"  # a sink bug is not a service outage


async def test_overlapping_trigger_is_skipped(cn: ConnectorsHarness) -> None:
    service_id = await cn.enabled()
    async with cn.full.database.engine.connect() as holder:
        await holder.execute(
            text("SELECT pg_advisory_lock(hashtextextended(:k, 0))"), {"k": f"connectors.sync:{service_id}"}
        )
        assert await cn.module.runner.run(service_id) is None
        with pytest.raises(SyncInProgress):
            await cn.module.runner.run(service_id, kind="manual")
        await holder.execute(
            text("SELECT pg_advisory_unlock(hashtextextended(:k, 0))"), {"k": f"connectors.sync:{service_id}"}
        )
        await holder.commit()
    assert await cn.module.runner.run(service_id) is not None


async def test_concurrent_runs_one_wins(cn: ConnectorsHarness) -> None:
    service_id = await cn.enabled()
    cn.remote.put("a", at=1)
    cn.remote.latency_seconds = 0.1
    results = await asyncio.gather(*(cn.module.runner.run(service_id) for _ in range(3)))
    assert sum(result is not None for result in results) >= 1
    assert cn.sink.calls.count(1) == sum(result is not None and result.added == 1 for result in results)


async def test_scheduler_enqueues_due_and_handles_job(cn: ConnectorsHarness) -> None:
    service_id = await cn.enabled()
    cn.remote.put("a", at=1)
    assert await cn.module.scheduler.enqueue_due() == 1
    assert await cn.module.scheduler.enqueue_due() == 0  # same window: deduplicated
    async with cn.full.database.session() as session:
        payload = await session.scalar(
            text("SELECT payload FROM core.job WHERE kind = 'connectors.sync_service' LIMIT 1")
        )
    await cn.module.scheduler.handle(payload)
    assert set(cn.sink.stored(await _ref(cn, service_id))) == {"a"}  # type: ignore[arg-type]
    assert await cn.module.scheduler.enqueue_due() == 0  # next run is in the future now


async def test_progress_is_visible_while_running_and_cleared_after(cn: ConnectorsHarness) -> None:
    """027: the services page shows how far a running sync got (records read so far, total if known)."""
    cn.module.config = replace(cn.module.config, sync_batch_size=2)
    service_id = await cn.enabled()
    for index in range(5):
        cn.remote.put(f"i{index}", at=index + 1)
    seen: list[dict[str, object] | None] = []
    upsert = cn.sink.upsert

    async def spying(records: list[object], ref: object) -> object:
        async with cn.full.database.session() as session:
            state = await session.get(SyncState, service_id)
            seen.append(dict(state.progress) if state and state.progress else None)
            view = await cn.module.manager.get(service_id)
        assert view.sync["progress"] == seen[-1]  # exposed on the service while running
        return await upsert(records, ref)  # type: ignore[arg-type]

    cn.sink.upsert = spying  # type: ignore[method-assign]
    await cn.module.runner.run(service_id, kind="manual")
    assert [p["done"] if p else None for p in seen] == [0, 2, 4]
    assert all(p and p["capability"] == "demo.items" and p["started_at"] for p in seen)
    async with cn.full.database.session() as session:
        state = await session.get(SyncState, service_id)
    assert (
        state is not None
        and state.progress is None
        and (await cn.module.manager.get(service_id)).sync["progress"] is None
    )


async def test_driven_capability_reports_progress(cn: ConnectorsHarness) -> None:
    """027: a capability the consuming module pulls itself (history, metadata) is synced from the services
    page like the others: the runner calls its driver, keeps its progress live and records the run."""
    seen: list[dict[str, object] | None] = []

    class _Driver:
        async def drive(self, service: ServiceRef, kind: str, report: Report) -> SinkResult:
            await report(1, 3)
            async with cn.full.database.session() as session:
                state = await session.get(SyncState, service.service_id)
            seen.append(state.progress if state else None)
            await report(3, 3)
            return SinkResult(modified=2, ignored=1)

    connector = cn.connectors.get("fake")
    assert connector is not None
    connector.provides = (CapabilityBinding(SPEC, driven=True),)  # type: ignore[misc]
    cn.sinks.register_driver(SPEC.name, _Driver(), owner="test:connectors")
    service_id = await cn.enabled()
    assert next(c for c in cn.module.manager.catalog() if c["key"] == "fake")["syncable"] == [SPEC.name]
    outcome = await cn.module.runner.run(service_id, kind="manual")
    assert outcome is not None and (outcome.status, outcome.modified, outcome.ignored) == ("succeeded", 2, 1)
    assert seen[0] is not None and (seen[0]["done"], seen[0]["total"]) == (1, 3)
    async with cn.full.database.session() as session:
        state = await session.get(SyncState, service_id)
    assert state is not None and state.status == "idle" and state.progress is None
