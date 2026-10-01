"""T031 — job deduplication: unique (queue, dedup_key); second enqueue is a no-op; no timestamp-only keys."""

import pytest

from portalab.core.db import Database
from portalab.core.jobs.registry import JobRegistry
from portalab.core.jobs.worker import Worker
from tests.integration.jobs_helpers import add_job, all_jobs, clock


async def test_second_enqueue_with_same_key_is_a_noop(database: Database) -> None:
    clk = clock()
    first = await add_job(database, clk, dedup_key="media.playback_finished:evt-1")
    second = await add_job(database, clk, dedup_key="media.playback_finished:evt-1")
    assert first.created is True
    assert second.created is False
    assert second.job_id == first.job_id
    assert len(await all_jobs(database)) == 1


async def test_same_key_in_another_queue_is_distinct(database: Database) -> None:
    clk = clock()
    await add_job(database, clk, dedup_key="k-1", queue="events")
    await add_job(database, clk, dedup_key="k-1", queue="notifications")
    assert len(await all_jobs(database)) == 2


async def test_jobs_without_dedup_key_are_never_deduplicated(database: Database) -> None:
    clk = clock()
    await add_job(database, clk)
    await add_job(database, clk)
    assert len(await all_jobs(database)) == 2


@pytest.mark.parametrize(
    "key", ["2026-10-01T12:00:00Z", "2026-10-01 12:00:00+00:00", "1790000000", "1790000000.123"]
)
async def test_timestamp_only_dedup_keys_are_rejected(database: Database, key: str) -> None:
    with pytest.raises(ValueError, match="timestamp"):
        await add_job(database, clock(), dedup_key=key)


async def test_payload_must_not_carry_secrets(database: Database) -> None:
    with pytest.raises(ValueError, match="secret"):
        await add_job(database, clock(), payload={"service_id": "x", "api_key": "abc"})


async def test_deduplicated_job_runs_once(database: Database) -> None:
    clk = clock()
    runs: list[str] = []
    registry = JobRegistry()

    @registry.handler("demo.count", idempotency="keyed by dedup_key; counting twice would be a bug")
    async def count(payload: dict[str, str]) -> None:
        runs.append(payload["n"])

    for _ in range(3):
        await add_job(database, clk, kind="demo.count", payload={"n": "1"}, dedup_key="count:1")
    worker = Worker(database, registry, worker_id="w1", clock=clk)
    assert await worker.run_once() == 1
    assert await worker.run_once() == 0
    assert runs == ["1"]
