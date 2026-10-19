"""``portalab worker`` wiring: database, handler registry, graceful shutdown on SIGTERM/SIGINT."""

import asyncio
import contextlib
import signal
from pathlib import Path

from portalab.app.composition import import_all_models
from portalab.app.wiring import Platform, wire_platform
from portalab.capabilities.catalog import new_registry
from portalab.core.db import Database
from portalab.core.jobs.queue import QUEUES
from portalab.core.jobs.registry import default_registry
from portalab.core.jobs.worker import Worker
from portalab.core.logging import get_logger
from portalab.core.settings import BootstrapSettings
from portalab.modules.authz.audit.offsite import BATCH, FILE_KEY, SYSLOG_KEY, AuditCopier

log = get_logger("portalab.worker")
SCHEDULE_RETRY_SECONDS = 5.0


async def schedule_sweeps(platform: Platform, stop: asyncio.Event) -> None:
    """Seed the periodic jobs; retried until the database is reachable (never fatal)."""
    while not stop.is_set():
        try:
            await platform.refresh_config()
            await platform.seed_periodic_jobs()
            return
        except Exception:
            log.warning("sweep scheduling failed, will retry")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=SCHEDULE_RETRY_SECONDS)


DISPATCH_INTERVAL_SECONDS = 1.0
SERVICES_REFRESH_SECONDS = 60.0


async def provide_services(platform: Platform, stop: asyncio.Event) -> None:
    """Provide the capabilities of the enabled services in the worker too (images, playback, requests run
    here), and pick up the services enabled from the web process since the last round."""
    while not stop.is_set():
        if not await platform.start_services():
            log.warning("service providers could not be refreshed, will retry")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=SERVICES_REFRESH_SECONDS)


async def dispatch_events(platform: Platform, stop: asyncio.Event) -> None:
    """Fan stored events out to their consumers (spec 007), independently of the job queue."""
    while not stop.is_set():
        try:
            await platform.events.dispatcher.run_once()
        except Exception:
            log.warning("event dispatch round failed, will retry")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=DISPATCH_INTERVAL_SECONDS)


AUDIT_COPY_SECONDS = 5.0


async def copy_audit(platform: Platform, database: Database, data_dir: Path, stop: asyncio.Event) -> None:
    """030 (FR-026): the audit trail copied off the machine as it is written (when a sink is configured)."""
    copier = AuditCopier(database, data_dir)
    while not stop.is_set():
        try:
            config = platform.administration.config
            file = str((await config.get(FILE_KEY)).value or "")
            syslog = str((await config.get(SYSLOG_KEY)).value or "")
            while await copier.run_once(file=file, syslog=syslog) == BATCH:
                pass  # catching up
        except Exception:
            log.warning("audit copy failed, will retry")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=AUDIT_COPY_SECONDS)


async def run_worker(settings: BootstrapSettings) -> None:
    import_all_models()
    database = Database.from_url(settings.database_url.reveal())
    capabilities = new_registry()
    platform = wire_platform(
        database,
        data_dir=settings.data_dir,
        capabilities=capabilities,
        secret_key=settings.secret_key,
        jobs=default_registry,
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stop.set)
    scheduler = asyncio.create_task(schedule_sweeps(platform, stop))
    dispatcher = asyncio.create_task(dispatch_events(platform, stop))
    services = asyncio.create_task(provide_services(platform, stop))
    audit = asyncio.create_task(copy_audit(platform, database, Path(settings.data_dir), stop))
    journal = asyncio.create_task(platform.observability.logs.run("worker", stop))  # issue 158
    try:
        await Worker(database, default_registry, queues=QUEUES).run_forever(stop)
    finally:
        stop.set()
        await scheduler
        await dispatcher
        await services
        await audit
        await journal
        await platform.plugins.runtime.stop_all()  # 030: no confined plugin process outlives the worker
        await database.dispose()
