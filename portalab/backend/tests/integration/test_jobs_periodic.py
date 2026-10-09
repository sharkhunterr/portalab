"""027 — periodic jobs keep running: a job run more often than once a minute (the playback poll, every
15 s) books its next slot — not its own, taken — and a failed run still books the next one."""

from datetime import timedelta

import pytest

from portalab.core.db import Database
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.registry import JobRegistry
from tests.integration.jobs_helpers import all_jobs, clock

pytestmark = pytest.mark.integration


async def test_a_job_every_15_seconds_books_each_next_slot(database: Database) -> None:
    clk = clock()
    registry = JobRegistry()
    runs: list[int] = []

    async def poll() -> None:
        runs.append(1)

    seed = register_periodic(
        registry, database, "demo.poll", timedelta(seconds=15), poll, owner="core", clock=clk
    )
    await seed()
    handler = registry.get("demo.poll")
    assert handler is not None
    for _ in range(3):  # three runs within the same minute
        await handler.func({})
        clk.advance(timedelta(seconds=15))
    keys = sorted(j.dedup_key for j in await all_jobs(database) if j.kind == "demo.poll")
    assert len(keys) == 4 and len(set(keys)) == 4  # the seed and one next slot per run


async def test_a_failed_run_still_books_the_next_one(database: Database) -> None:
    clk = clock()
    registry = JobRegistry()

    async def poll() -> None:
        raise RuntimeError("the service is down")

    seed = register_periodic(
        registry, database, "demo.down", timedelta(minutes=10), poll, owner="core", clock=clk
    )
    await seed()
    handler = registry.get("demo.down")
    assert handler is not None
    with pytest.raises(RuntimeError):
        await handler.func({})
    assert len([j for j in await all_jobs(database) if j.kind == "demo.down"]) == 2
