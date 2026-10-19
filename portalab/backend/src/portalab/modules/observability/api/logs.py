"""The log journal API (issue 158): the administrators read the server's and the worker's log lines (already
redacted), newest first, filtered, live (``after``) or back in time (``before``), and export a selection as
text or JSON. A permission of its own (``observability.logs.read``, administrators only); readings and
exports are audited."""

import json
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.modules.observability.api.routes import Module
from portalab.modules.observability.logs.service import LEVELS, LogFilter
from portalab.modules.observability.models import LogEntry
from portalab.modules.observability.permissions import OBSERVABILITY_LOGS

router = APIRouter(prefix="/api/v1/admin/observability", tags=["observability"])

LogReader = Annotated[Principal, require(OBSERVABILITY_LOGS)]
Level = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class LogLineOut(BaseModel):
    seq: int
    at: datetime
    process: str
    level: str
    logger: str
    source: str
    message: str
    correlation_id: str | None
    fields: dict[str, Any]


class LogsOut(BaseModel):
    items: list[LogLineOut]
    sources: list[str] | None  # on a first page only (not on every live refresh)
    levels: list[str]


def _out(entry: LogEntry) -> LogLineOut:
    return LogLineOut(
        seq=entry.seq,
        at=entry.at,
        process=entry.process,
        level=entry.level,
        logger=entry.logger,
        source=entry.source,
        message=entry.message,
        correlation_id=entry.correlation_id,
        fields=entry.fields or {},
    )


def _filter(
    level: list[Level] | None,
    source: list[str] | None,
    exclude: list[str] | None,
    process: str | None,
    q: str | None,
    since: datetime | None,
    until: datetime | None,
    correlation: str | None,
) -> LogFilter:
    return LogFilter(
        levels=tuple(level or ()),
        sources=tuple(s for s in (source or ()) if s),
        excluded=tuple(s for s in (exclude or ()) if s),
        process=process or None,
        text=(q or "").strip()[:200] or None,
        since=since,
        until=until,
        correlation_id=(correlation or "").strip()[:64] or None,
    )


@router.get("/logs", response_model=LogsOut)
async def read_logs(
    principal: LogReader,
    module: Module,
    level: Annotated[list[Level] | None, Query()] = None,
    source: Annotated[list[str] | None, Query()] = None,
    exclude: Annotated[list[str] | None, Query()] = None,
    process: Annotated[str | None, Query(max_length=32)] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    since: datetime | None = None,
    until: datetime | None = None,
    correlation: Annotated[str | None, Query(max_length=64)] = None,
    before: Annotated[int | None, Query(ge=1)] = None,
    after: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> LogsOut:
    wanted = _filter(level, source, exclude, process, q, since, until, correlation)
    if after is None:
        await module.logs.viewed(principal, wanted)
    lines = await module.logs.lines(wanted, limit=limit, before=before, after=after)
    first = before is None and after is None
    return LogsOut(
        items=[_out(line) for line in lines],
        sources=await module.logs.sources() if first else None,
        levels=list(LEVELS),
    )


def _text(line: LogLineOut) -> str:
    extra = {k: v for k, v in line.fields.items() if k != "exception"}
    head = f"{line.at.isoformat()} {line.level:<8} {line.process:<6} [{line.source}] {line.message}"
    if line.correlation_id:
        head += f" (correlation {line.correlation_id})"
    if extra:
        head += " " + json.dumps(extra, ensure_ascii=False, default=str)
    exception = line.fields.get("exception")
    return head + (f"\n{exception}" if isinstance(exception, str) else "")


@router.get(
    "/logs/export",
    response_class=Response,
    responses={200: {"content": {"text/plain": {}, "application/json": {}}}},
)
async def export_logs(
    principal: LogReader,
    module: Module,
    format: Literal["text", "json"] = "text",
    level: Annotated[list[Level] | None, Query()] = None,
    source: Annotated[list[str] | None, Query()] = None,
    exclude: Annotated[list[str] | None, Query()] = None,
    process: Annotated[str | None, Query(max_length=32)] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    since: datetime | None = None,
    until: datetime | None = None,
    correlation: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=5_000)] = 2_000,
) -> Response:
    """The selection as a file (oldest first, as a log reads), at most 5,000 lines."""
    wanted = _filter(level, source, exclude, process, q, since, until, correlation)
    await module.logs.viewed(principal, wanted, export=format)
    lines = [_out(line) for line in reversed(await module.logs.lines(wanted, limit=limit))]
    if format == "json":
        body = json.dumps([line.model_dump(mode="json") for line in lines], ensure_ascii=False, indent=1)
        media, extension = "application/json", "json"
    else:
        body = "\n".join(_text(line) for line in lines) + ("\n" if lines else "")
        media, extension = "text/plain; charset=utf-8", "log"
    return Response(
        body,
        media_type=media,
        headers={"content-disposition": f'attachment; filename="portalab-logs.{extension}"'},
    )
