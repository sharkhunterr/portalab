"""``GET /api/v1/stream`` — Server-Sent Events fed from the ``core.live_event`` outbox (research R5).

* authorization required (``stream.subscribe``), then every event is filtered per subscriber: audience user
  and/or permission (+ resource) through the Authorizer port — nothing a caller may not see is sent;
* a fresh connection starts at the current tip; ``Last-Event-ID`` (header, or ``?last_event_id=``) resumes
  after a given event;
* each connection polls independently, so a slow consumer never blocks producers or other consumers;
* heartbeats (SSE comments) keep idle connections open through proxies.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from portalab.core.authorization import current_principal, require
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.core.errors import Unavailable
from portalab.core.live import LiveEvent, fetch_after, latest_seq

router = APIRouter(prefix="/api/v1", tags=["stream"])


@dataclass(frozen=True, slots=True)
class StreamOptions:
    poll_interval_seconds: float = 1.0
    heartbeat_seconds: float = 15.0
    batch_size: int = 200
    retry_milliseconds: int = 3000


async def _visible(event: LiveEvent, principal: Principal, authorizer: Authorizer) -> bool:
    if event.audience_user_id is not None and event.audience_user_id != principal.user_id:
        return False
    if event.permission is None:
        return True
    return await authorizer.is_allowed(principal, event.permission, event.resource)


def _frame(event: LiveEvent) -> str:
    data = json.dumps(event.payload, ensure_ascii=False, separators=(", ", ": "))
    return f"id: {event.seq}\nevent: {event.topic}\ndata: {data}\n\n"


def _parse_last_event_id(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    try:
        return max(int(value), 0)
    except ValueError:
        return None


async def event_stream(
    database: Database,
    principal: Principal,
    authorizer: Authorizer,
    *,
    last_event_id: str | None,
    options: StreamOptions,
    is_disconnected: Callable[[], Awaitable[bool]] | None = None,
) -> AsyncIterator[str]:
    cursor = _parse_last_event_id(last_event_id)
    if cursor is None:
        async with database.session() as session:
            cursor = await latest_seq(session)
    yield f"retry: {options.retry_milliseconds}\n\n"
    loop = asyncio.get_running_loop()
    last_sent = loop.time()
    while True:
        if is_disconnected is not None and await is_disconnected():
            return
        async with database.session() as session:
            events = await fetch_after(session, cursor, options.batch_size)
        for event in events:
            cursor = int(event.seq)
            if await _visible(event, principal, authorizer):
                yield _frame(event)
                last_sent = loop.time()
        if len(events) < options.batch_size:
            if loop.time() - last_sent >= options.heartbeat_seconds:
                yield ": keepalive\n\n"
                last_sent = loop.time()
            await asyncio.sleep(options.poll_interval_seconds)


@router.get(
    "/stream",
    dependencies=[require("stream.subscribe")],
    summary="Live notifications (SSE)",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}, "description": "SSE stream"},
        401: {"description": "Authentication required (problem+json)"},
        403: {"description": "Not allowed (problem+json)"},
    },
)
async def stream(request: Request) -> StreamingResponse:
    database: Database | None = request.app.state.database
    if database is None:
        raise Unavailable("Live updates are temporarily unavailable.", code="stream.unavailable")
    principal = await current_principal(request)
    generator = event_stream(
        database,
        principal,
        request.app.state.authorizer,
        # EventSource cannot set headers on a manual reconnect: accept the query parameter as a fallback
        last_event_id=request.headers.get("Last-Event-ID") or request.query_params.get("last_event_id"),
        options=request.app.state.stream_options,
        is_disconnected=request.is_disconnected,
    )
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
