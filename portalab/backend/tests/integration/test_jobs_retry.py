"""T033 — retry with backoff, max_attempts → dead, redacted last_error, failures never block other jobs."""

from datetime import timedelta

from portalab.core.db import Database
from portalab.core.jobs.queue import backoff_seconds, claim, fail
from portalab.core.jobs.registry import JobRegistry
from portalab.core.jobs.worker import Worker
from tests.integration.jobs_helpers import add_job, all_jobs, clock


def test_backoff_schedule_is_exponential_and_capped() -> None:
    assert [backoff_seconds(n) for n in (1, 2, 3, 4)] == [5, 10, 20, 40]
    assert backoff_seconds(30) == 3600


async def test_failure_backs_off_then_goes_dead(database: Database) -> None:
    clk = clock()
    await add_job(database, clk, max_attempts=3)
    for attempt in (1, 2, 3):
        jobs = await claim(database, queue="default", worker_id="w", clock=clk)
        assert len(jobs) == 1 and jobs[0].attempts == attempt
        await fail(database, jobs[0].id, worker_id="w", error="boom", clock=clk)
        (job,) = await all_jobs(database)
        if attempt < 3:
            assert job.status == "queued"
            assert job.run_at == clk.now() + timedelta(seconds=backoff_seconds(attempt))
            clk.set(job.run_at)
        else:
            assert job.status == "dead"
    assert await claim(database, queue="default", worker_id="w", clock=clk) == []


async def test_last_error_is_redacted_and_truncated(database: Database) -> None:
    clk = clock()
    await add_job(database, clk, max_attempts=1)
    (job,) = await claim(database, queue="default", worker_id="w", clock=clk)
    await fail(database, job.id, worker_id="w", error="auth failed password=hunter2 " + "x" * 5000, clock=clk)
    (stored,) = await all_jobs(database)
    assert stored.status == "dead"
    assert stored.last_error is not None
    assert "hunter2" not in stored.last_error
    assert len(stored.last_error) <= 2000


async def test_a_failing_handler_never_blocks_other_jobs(database: Database) -> None:
    clk = clock()
    done: list[str] = []
    registry = JobRegistry()

    @registry.handler("demo.fail", idempotency="pure failure, no side effects")
    async def failing(payload: dict[str, str]) -> None:
        raise RuntimeError("token=abcdef123456 exploded")

    @registry.handler("demo.ok", idempotency="appends once per job id in this test")
    async def ok(payload: dict[str, str]) -> None:
        done.append(payload["name"])

    @registry.handler("demo.slow", idempotency="no side effects", timeout_seconds=0.05)
    async def slow(payload: dict[str, str]) -> None:
        import asyncio

        await asyncio.sleep(5)

    await add_job(database, clk, kind="demo.fail", max_attempts=1)
    await add_job(database, clk, kind="demo.slow", max_attempts=1)
    await add_job(database, clk, kind="demo.ok", payload={"name": "after"})
    await add_job(database, clk, kind="demo.unknown", max_attempts=1)
    worker = Worker(database, registry, worker_id="w", clock=clk, batch_size=10)
    assert await worker.run_once() == 4
    assert done == ["after"]
    statuses = {job.kind: job.status for job in await all_jobs(database)}
    assert statuses == {
        "demo.fail": "dead",
        "demo.slow": "dead",
        "demo.ok": "succeeded",
        "demo.unknown": "dead",
    }
    failed = next(job for job in await all_jobs(database) if job.kind == "demo.fail")
    assert failed.last_error is not None and "abcdef123456" not in failed.last_error
