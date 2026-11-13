"""Issue 401 — the portal served for the API fuzzer (Schemathesis): the real application on its database,
with its intrusion guard and rate limits out of the way — the fuzzer probes every route on purpose, and
both are tested apart. Never used in production (it lives with the tests).

    DATABASE_URL=… SECRET_KEY=… uv run python -m tests.fuzz.serve PORT
"""

import asyncio
import contextvars
import faulthandler
import io
import sys
import threading
import time

import uvicorn
from sqlalchemy import event
from sqlalchemy.engine import Engine

from portalab.app.main import create_app, guard_of
from portalab.core.logging import configure_logging
from portalab.core.settings import load_settings
from portalab.modules.privacy.settings import SecurityConfig

UNLIMITED = 10**9
# issue 404: the SQL statements each request ran, told in « X-Query-Count » (N+1 hunting)
QUERIES: contextvars.ContextVar[list[int] | None] = contextvars.ContextVar("queries", default=None)


@event.listens_for(Engine, "before_cursor_execute")
def _count(*_args: object) -> None:
    counter = QUERIES.get()
    if counter is not None:
        counter[0] += 1


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
    settings = load_settings()
    configure_logging("WARNING")
    app = create_app(
        settings,
        static_dir=None,
        security_config=SecurityConfig(
            rate_limit_per_ip_per_minute=UNLIMITED,
            rate_limit_per_user_per_minute=UNLIMITED,
            rate_limit_sign_in_per_minute=UNLIMITED,
        ),
    )
    guard_of(app).enabled = False

    async def watchdog() -> None:
        """A request that holds the event loop (a slow regular expression, a big computation) stops every
        other: when the loop has not answered for 5 s, the stack of what holds it is written out."""
        loop = asyncio.get_running_loop()
        beat = [time.monotonic()]

        def tick() -> None:
            beat[0] = time.monotonic()

        def watch() -> None:
            dumped = 0.0
            while True:
                time.sleep(1)
                loop.call_soon_threadsafe(tick)
                stalled = time.monotonic() - beat[0]
                if stalled > 5 and time.monotonic() - dumped > 10:
                    sys.stderr.write(f"\n=== event loop held for {stalled:.0f} s ===\n")
                    faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
                    dumped = time.monotonic()

        threading.Thread(target=watch, daemon=True).start()

        async def slow_requests() -> None:
            """A request waiting more than 20 s: where every task waits, once a minute at most."""
            dumped = 0.0
            while True:
                await asyncio.sleep(2)
                oldest = min(started.values(), default=time.monotonic())
                if time.monotonic() - oldest > 20 and time.monotonic() - dumped > 60:
                    out = io.StringIO()
                    out.write(f"\n=== a request waits for {time.monotonic() - oldest:.0f} s ===\n")
                    for task in asyncio.all_tasks():
                        task.print_stack(limit=25, file=out)
                    sys.stderr.write(out.getvalue())
                    dumped = time.monotonic()

        background.add(asyncio.create_task(slow_requests()))

    started: dict[int, float] = {}
    background: set[asyncio.Task[None]] = set()

    @app.middleware("http")
    async def timed(request, call_next):  # type: ignore[no-untyped-def]
        if (
            not background
        ):  # the app's own lifespan runs no startup hook: the watch starts with the first request
            await watchdog()
        started[id(request)] = time.monotonic()
        counter = [0]
        QUERIES.set(counter)
        try:
            response = await call_next(request)
            response.headers["X-Query-Count"] = str(counter[0])
            return response
        finally:
            started.pop(id(request), None)

    uvicorn.run(app, host="127.0.0.1", port=port, log_config=None, access_log=False)


if __name__ == "__main__":
    main()
