"""``portalab worker`` wiring: database, handler registry, graceful shutdown on SIGTERM/SIGINT."""

import asyncio
import contextlib
import signal

from portalab.app.composition import import_all_models
from portalab.app.wiring import Platform, wire_platform
from portalab.capabilities.catalog import new_registry
from portalab.core.db import Database
from portalab.core.jobs.registry import default_registry
from portalab.core.jobs.worker import Worker
from portalab.core.logging import get_logger
from portalab.core.settings import BootstrapSettings

log = get_logger("portalab.worker")
SCHEDULE_RETRY_SECONDS = 5.0


async def schedule_sweeps(platform: Platform, stop: asyncio.Event) -> None:
    """Seed the periodic jobs; retried until the database is reachable (never fatal)."""
    while not stop.is_set():
        try:
            await platform.seed_periodic_jobs()
            return
        except Exception:
            log.warning("sweep scheduling failed, will retry")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=SCHEDULE_RETRY_SECONDS)


async def run_worker(settings: BootstrapSettings) -> None:
    import_all_models()
    database = Database.from_url(settings.database_url.reveal())
    capabilities = new_registry()
    platform = wire_platform(
        database, data_dir=settings.data_dir, capabilities=capabilities, jobs=default_registry
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stop.set)
    scheduler = asyncio.create_task(schedule_sweeps(platform, stop))
    try:
        await Worker(database, default_registry).run_forever(stop)
    finally:
        stop.set()
        await scheduler
        await database.dispose()
