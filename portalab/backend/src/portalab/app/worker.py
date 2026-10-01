"""``portalab worker`` wiring: database, handler registry, graceful shutdown on SIGTERM/SIGINT."""

import asyncio
import signal

from portalab.app.composition import import_all_models
from portalab.core.db import Database
from portalab.core.jobs.registry import default_registry
from portalab.core.jobs.worker import Worker
from portalab.core.settings import BootstrapSettings


async def run_worker(settings: BootstrapSettings) -> None:
    import_all_models()
    database = Database.from_url(settings.database_url.reveal())
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stop.set)
    try:
        await Worker(database, default_registry).run_forever(stop)
    finally:
        await database.dispose()
