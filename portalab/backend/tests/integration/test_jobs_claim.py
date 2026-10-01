"""T032 — concurrent workers never claim the same job (SKIP LOCKED); expired locks are re-claimed."""

import asyncio
from datetime import timedelta

from portalab.core.db import Database
from portalab.core.jobs.queue import claim, succeed
from tests.integration.jobs_helpers import add_job, all_jobs, clock


async def test_concurrent_claims_are_disjoint(database: Database) -> None:
    clk = clock()
    for _ in range(20):
        await add_job(database, clk)
    batches = await asyncio.gather(
        *(claim(database, queue="default", worker_id=f"w{i}", limit=8, clock=clk) for i in range(4))
    )
    claimed = [job.id for batch in batches for job in batch]
    assert len(claimed) == len(set(claimed)) == 20


async def test_future_jobs_are_not_claimed_early(database: Database) -> None:
    clk = clock()
    await add_job(database, clk, run_at=clk.now() + timedelta(minutes=5))
    assert await claim(database, queue="default", worker_id="w1", clock=clk) == []
    clk.advance(timedelta(minutes=5))
    assert len(await claim(database, queue="default", worker_id="w1", clock=clk)) == 1


async def test_expired_lock_is_reclaimed_after_a_crash(database: Database) -> None:
    clk = clock()
    await add_job(database, clk)
    first = await claim(database, queue="default", worker_id="crashed", lock_seconds=30, clock=clk)
    assert len(first) == 1
    # the worker crashes: no succeed/fail; before expiry nobody else can take it
    assert await claim(database, queue="default", worker_id="other", clock=clk) == []
    clk.advance(timedelta(seconds=31))
    second = await claim(database, queue="default", worker_id="other", clock=clk)
    assert [job.id for job in second] == [first[0].id]
    assert second[0].attempts == 2
    # the crashed worker coming back late cannot complete a job it no longer owns
    assert await succeed(database, first[0].id, worker_id="crashed", clock=clk) is False
    assert await succeed(database, first[0].id, worker_id="other", clock=clk) is True
    assert [job.status for job in await all_jobs(database)] == ["succeeded"]
