"""T049 — GET /api/v1/stream (SSE): authorization required, permission-filtered, Last-Event-ID resume,
slow consumers never block producers, heartbeats keep idle connections alive."""

import asyncio
import contextlib
import json
import socket
import time
from uuid import uuid4

import httpx
import uvicorn
from fastapi import Request

from portalab.app.main import create_app
from portalab.app.stream import StreamOptions, event_stream
from portalab.core.authz_port import DenyAllAuthorizer, Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.live import publish_live

ALICE = uuid4()
BOB = uuid4()


class GrantOnly:
    """Allows ``stream.subscribe`` and the listed permissions."""

    def __init__(self, *permissions: str) -> None:
        self.permissions = {"stream.subscribe", *permissions}

    async def is_allowed(
        self, principal: Principal, permission: str, resource: ResourceRef | None = None
    ) -> bool:
        return principal.is_authenticated and permission in self.permissions


class FixedPrincipal:
    def __init__(self, principal: Principal) -> None:
        self.principal = principal

    async def resolve(self, request: Request) -> Principal:
        return self.principal


FAST = StreamOptions(poll_interval_seconds=0.05, heartbeat_seconds=0.2, batch_size=50)


async def _publish_sample(database: Database) -> list[int]:
    async with database.unit_of_work() as uow:
        public = await publish_live(uow.session, topic="portal.ping", payload={"n": 1})
        media = await publish_live(
            uow.session,
            topic="media.updated",
            payload={"object_id": "m1"},
            permission="media.read",
            resource=ResourceRef(kind="media", id="m1"),
        )
        private = await publish_live(
            uow.session, topic="notification.created", payload={"id": "n1"}, audience_user_id=BOB
        )
    return [public, media, private]


async def _collect(generator: object, count: int, limit_seconds: float = 3.0) -> list[str]:
    frames: list[str] = []

    async def run() -> None:
        async for frame in generator:  # type: ignore[attr-defined]
            if not frame.startswith((":", "retry:")):
                frames.append(frame)
            if len(frames) >= count:
                return

    await asyncio.wait_for(run(), timeout=limit_seconds)
    return frames


def _parse(frame: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in frame.strip().splitlines():
        key, _, value = line.partition(": ")
        fields[key] = value
    return fields


async def test_stream_requires_authorization(database: Database, heads: set[str]) -> None:
    for principal, expected in ((Principal(), 401), (Principal(user_id=ALICE), 403)):
        app = create_app(
            database=database,
            migration_heads=heads,
            principal_resolver=FixedPrincipal(principal),
            authorizer=DenyAllAuthorizer(),  # holders of stream.subscribe: see the authz permission matrix
        )
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
            assert (await client.get("/api/v1/stream")).status_code == expected


async def _subscribe(database: Database, principal: Principal, authorizer: GrantOnly) -> object:
    """Open a fresh subscription (starts at the current tip) and consume its ``retry`` preamble."""
    generator = event_stream(database, principal, authorizer, last_event_id=None, options=FAST)
    assert (await generator.__anext__()).startswith("retry:")
    return generator


async def test_new_subscription_starts_at_the_current_tip(database: Database) -> None:
    await _publish_sample(database)  # published before connecting: not replayed
    generator = await _subscribe(database, Principal(user_id=ALICE), GrantOnly("media.read"))
    async with database.unit_of_work() as uow:
        fresh = await publish_live(uow.session, topic="portal.fresh", payload={})
    frames = await _collect(generator, count=1)
    assert _parse(frames[0])["id"] == str(fresh)


async def test_events_are_filtered_by_permission_and_audience(database: Database) -> None:
    alice_media = await _subscribe(database, Principal(user_id=ALICE), GrantOnly("media.read"))
    alice_plain = await _subscribe(database, Principal(user_id=ALICE), GrantOnly())
    bob = await _subscribe(database, Principal(user_id=BOB), GrantOnly())
    public, media, _private = await _publish_sample(database)

    parsed = [_parse(frame) for frame in await _collect(alice_media, count=2)]
    assert [p["id"] for p in parsed] == [str(public), str(media)]
    assert [p["event"] for p in parsed] == ["portal.ping", "media.updated"]
    assert json.loads(parsed[1]["data"]) == {"object_id": "m1"}

    async with database.unit_of_work() as uow:
        marker = await publish_live(uow.session, topic="portal.marker", payload={})
    plain = [_parse(f) for f in await _collect(alice_plain, count=2)]
    assert [p["event"] for p in plain] == ["portal.ping", "portal.marker"]
    assert plain[1]["id"] == str(marker)

    bob_frames = [_parse(f)["event"] for f in await _collect(bob, count=2)]
    assert bob_frames == ["portal.ping", "notification.created"]


async def test_last_event_id_resumes_after_the_given_event(database: Database) -> None:
    public, media, _ = await _publish_sample(database)
    frames = await _collect(
        event_stream(
            database,
            Principal(user_id=ALICE),
            GrantOnly("media.read"),
            last_event_id=str(public),
            options=FAST,
        ),
        count=1,
    )
    assert _parse(frames[0])["id"] == str(media)


async def test_heartbeat_when_idle(database: Database) -> None:
    generator = event_stream(database, Principal(user_id=ALICE), GrantOnly(), last_event_id="0", options=FAST)
    first = await asyncio.wait_for(generator.__anext__(), timeout=2)
    assert first.startswith("retry:")
    second = await asyncio.wait_for(generator.__anext__(), timeout=2)
    assert second.startswith(": keepalive")
    await generator.aclose()


async def test_slow_consumer_does_not_block_producers(database: Database) -> None:
    generator = event_stream(
        database, Principal(user_id=ALICE), GrantOnly(), last_event_id=None, options=FAST
    )
    await generator.__anext__()  # connected, then never read again
    started = time.monotonic()
    for batch in range(5):
        async with database.unit_of_work() as uow:
            for n in range(100):
                await publish_live(uow.session, topic="bulk", payload={"n": batch * 100 + n})
    assert time.monotonic() - started < 5
    await generator.aclose()


async def test_end_to_end_over_http(migrated_db_url: str, heads: set[str]) -> None:
    database = Database.from_url(migrated_db_url)
    app = create_app(
        database=database,
        migration_heads=heads,
        authorizer=GrantOnly(),
        principal_resolver=FixedPrincipal(Principal(user_id=ALICE)),
        stream_options=FAST,
    )
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_config=None, lifespan="off"))
    task = asyncio.create_task(server.serve())
    try:
        for _ in range(100):
            if server.started:
                break
            await asyncio.sleep(0.05)
        async with (
            httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=5) as client,
            client.stream("GET", "/api/v1/stream") as response,
        ):
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            async with database.unit_of_work() as uow:
                seq = await publish_live(uow.session, topic="portal.ping", payload={"hello": "world"})
            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk
                if f"id: {seq}" in buffer:
                    break
        assert '"hello": "world"' in buffer
    finally:
        server.should_exit = True
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=5)
        await database.dispose()
