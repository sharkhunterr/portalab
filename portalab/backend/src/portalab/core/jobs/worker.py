"""Background worker: poll → claim → run handler with timeout → succeed / fail (plan §6).

A failing, slow or unknown job never blocks the others; logs carry the job's correlation id.
"""

import asyncio
import contextlib
import os
import socket

from portalab.core.db import Database
from portalab.core.jobs.queue import DEFAULT_LOCK_SECONDS, DEFAULT_QUEUE, ClaimedJob, claim, fail, succeed
from portalab.core.jobs.registry import JobRegistry
from portalab.core.logging import correlation_scope, get_logger
from portalab.core.time import Clock

log = get_logger("portalab.worker")


def default_worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


class Worker:
    def __init__(
        self,
        database: Database,
        registry: JobRegistry,
        *,
        queues: tuple[str, ...] = (DEFAULT_QUEUE,),
        worker_id: str | None = None,
        batch_size: int = 10,
        lock_seconds: int = DEFAULT_LOCK_SECONDS,
        poll_interval: float = 1.0,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.registry = registry
        self.queues = queues
        self.worker_id = worker_id or default_worker_id()
        self.batch_size = batch_size
        self.lock_seconds = lock_seconds
        self.poll_interval = poll_interval
        self.clock = clock

    async def run_once(self) -> int:
        """Process one batch per queue; returns the number of jobs handled."""
        handled = 0
        for queue in self.queues:
            jobs = await claim(
                self.database,
                queue=queue,
                worker_id=self.worker_id,
                limit=self.batch_size,
                lock_seconds=self.lock_seconds,
                clock=self.clock,
            )
            for job in jobs:
                await self._execute(job)
                handled += 1
        return handled

    async def _execute(self, job: ClaimedJob) -> None:
        with correlation_scope(job.correlation_id):
            handler = self.registry.get(job.kind)
            context = {"job_id": str(job.id), "kind": job.kind, "attempt": job.attempts}
            if handler is None:
                log.error("no handler registered", extra={"fields": context})
                await fail(
                    self.database, job.id, worker_id=self.worker_id, error="no handler", clock=self.clock
                )
                return
            try:
                await asyncio.wait_for(handler.func(job.payload), timeout=handler.timeout_seconds)
            except TimeoutError:
                log.warning("job timed out", extra={"fields": context})
                await fail(self.database, job.id, worker_id=self.worker_id, error="timeout", clock=self.clock)
            except Exception as exc:
                log.warning("job failed", extra={"fields": {**context, "error": type(exc).__name__}})
                await fail(
                    self.database,
                    job.id,
                    worker_id=self.worker_id,
                    error=f"{type(exc).__name__}: {exc}",
                    clock=self.clock,
                )
            else:
                await succeed(self.database, job.id, worker_id=self.worker_id, clock=self.clock)

    async def run_forever(self, stop: asyncio.Event) -> None:
        log.info(
            "worker started", extra={"fields": {"worker_id": self.worker_id, "queues": list(self.queues)}}
        )
        while not stop.is_set():
            try:
                handled = await self.run_once()
            except Exception:
                log.exception("worker loop error (will retry)")
                handled = 0
            if handled == 0:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=self.poll_interval)
        log.info("worker stopped", extra={"fields": {"worker_id": self.worker_id}})
