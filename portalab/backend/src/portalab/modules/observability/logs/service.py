"""The log journal (issue 158).

Each process (the server, the worker) keeps its last log lines in ``core.logging.log_tap`` — already
redacted by the one formatter every line goes through — and stores them here every few seconds. The
administrators read them newest first, filter them (level, source, process, period, text, correlation id),
follow them live and export a selection. Bounded: a few days (retention target ``observability.logs``) and a
maximum count (trimmed every hour). Reading the journal is audited (once per administrator every few minutes,
and every export).
"""

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, delete, func, insert, select

from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.logging import LogTap, log_tap
from portalab.core.time import Clock, utc_now
from portalab.modules.observability.models import LogEntry
from portalab.modules.observability.settings import ObservabilityConfig

log = logging.getLogger(__name__)  # left out of the tap: the journal never journals itself

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
BASE_KEYS = frozenset({"timestamp", "level", "logger", "message", "correlation_id"})
MESSAGE_MAX = 8_000
FIELD_MAX = 20_000
VIEW_AUDIT_SECONDS = 300.0
HTTP_SOURCE = "http"  # the requests the server answered
OUTGOING_SOURCE = "http.out"  # the calls Portalab makes to the services (httpx)


def message_of(message: str, fields: dict[str, Any]) -> str:
    """A request line says what it was (« GET /api/v1/me → 200 · 12 ms »), not just « request »."""
    if message == "request" and {"method", "path", "status"} <= fields.keys():
        took = fields.get("duration_ms")
        return f"{fields['method']} {fields['path']} → {fields['status']}" + (
            f" · {took} ms" if took is not None else ""
        )
    return message


def source_of(logger: str, fields: dict[str, Any]) -> str:
    """Where a line comes from, as the administrators think of it: a module, a connector, an extension,
    the jobs, the server, the database."""
    plugin = fields.get("plugin")
    if isinstance(plugin, str) and plugin:
        return f"plugin:{plugin}"[:128]
    parts = logger.split(".")
    if logger == "portalab.app" and {"method", "path", "status"} <= fields.keys():
        return HTTP_SOURCE  # one line per request: hidden by default on the page
    if parts[0] == "portalab" and len(parts) > 1:
        if parts[1] == "modules" and len(parts) > 2:
            return parts[2]
        if parts[1] == "connectors" and len(parts) > 2:
            return f"connector:{parts[2]}"
        if parts[1] == "core" and parts[2:3] == ["jobs"]:
            return "jobs"
        return parts[1]
    if parts[0] in ("uvicorn", "starlette", "fastapi"):
        return "server"
    if parts[0] in ("httpx", "httpcore"):
        return OUTGOING_SOURCE
    if parts[0] in ("sqlalchemy", "asyncpg", "alembic"):
        return "database"
    return parts[0][:128] or "root"


def _parse_at(raw: Any, fallback: datetime) -> datetime:
    if isinstance(raw, str):
        with contextlib.suppress(ValueError):
            return datetime.fromisoformat(raw)
    return fallback


def _bounded(value: Any) -> Any:
    if isinstance(value, str) and len(value) > FIELD_MAX:
        return value[:FIELD_MAX] + "…"
    return value


@dataclass(frozen=True, slots=True)
class LogFilter:
    levels: Sequence[str] = ()
    sources: Sequence[str] = ()
    excluded: Sequence[str] = ()  # sources left out (the page hides the requests by default)
    process: str | None = None
    text: str | None = None
    since: datetime | None = None
    until: datetime | None = None
    correlation_id: str | None = None

    def context(self) -> dict[str, Any]:
        """What was asked, for the audit trail (no text searched: it may hold anything)."""
        return {
            "levels": list(self.levels),
            "sources": list(self.sources),
            "excluded": list(self.excluded),
            "process": self.process,
            "searched": bool(self.text),
            "since": self.since.isoformat() if self.since else None,
            "until": self.until.isoformat() if self.until else None,
        }


@dataclass(slots=True)
class LogJournal:
    database: Database
    audit: AuditSink
    config: Callable[[], ObservabilityConfig]
    clock: Clock | None = None
    tap: LogTap = log_tap
    _viewed: dict[UUID, float] = field(default_factory=dict)

    # --- storing ------------------------------------------------------------------------------------

    async def store(self, process: str) -> int:
        """Move this process's waiting lines into the journal; returns how many."""
        lines = self.tap.drain()
        if not lines:
            return 0
        now = utc_now(self.clock)
        rows = []
        for line in lines:
            fields = {k: _bounded(v) for k, v in line.items() if k not in BASE_KEYS}
            logger = str(line.get("logger") or "root")[:200]
            level = str(line.get("level") or "INFO").upper()[:16]
            rows.append(
                {
                    "at": _parse_at(line.get("timestamp"), now),
                    "process": process[:32],
                    "level": level,
                    "logger": logger,
                    "source": source_of(logger, fields),
                    "message": message_of(str(line.get("message") or ""), fields)[:MESSAGE_MAX],
                    "correlation_id": (
                        str(line["correlation_id"])[:64] if line.get("correlation_id") else None
                    ),
                    "fields": fields,
                }
            )
        try:
            async with self.database.unit_of_work() as uow:
                await uow.session.execute(insert(LogEntry), rows)
        except Exception:
            log.warning("log journal: %d lines could not be stored", len(rows))
            return 0
        return len(rows)

    async def run(self, process: str, stop: asyncio.Event | None = None, interval: float = 2.0) -> None:
        """Store this process's lines every ``interval`` seconds until ``stop`` (or cancellation)."""
        while stop is None or not stop.is_set():
            if stop is None:
                await asyncio.sleep(interval)
            else:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=interval)
            with contextlib.suppress(Exception):
                await self.store(process)

    async def trim(self) -> int:
        """Keep at most ``log_max_lines`` lines (the oldest go first)."""
        keep = max(1_000, self.config().log_max_lines)
        async with self.database.unit_of_work() as uow:
            newest = await uow.session.scalar(select(func.max(LogEntry.seq)))
            if newest is None:
                return 0
            result = await uow.session.execute(delete(LogEntry).where(LogEntry.seq <= newest - keep))
        return int(getattr(result, "rowcount", 0) or 0)

    # --- reading ------------------------------------------------------------------------------------

    def _filtered(self, query: Select[tuple[LogEntry]], wanted: LogFilter) -> Select[tuple[LogEntry]]:
        if wanted.levels:
            query = query.where(LogEntry.level.in_([level.upper() for level in wanted.levels]))
        if wanted.sources:
            query = query.where(LogEntry.source.in_(list(wanted.sources)))
        if wanted.excluded:
            query = query.where(LogEntry.source.not_in(list(wanted.excluded)))
        if wanted.process:
            query = query.where(LogEntry.process == wanted.process)
        if wanted.text:
            escaped = wanted.text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            query = query.where(LogEntry.message.ilike(f"%{escaped}%", escape="\\"))
        if wanted.since:
            query = query.where(LogEntry.at >= wanted.since)
        if wanted.until:
            query = query.where(LogEntry.at <= wanted.until)
        if wanted.correlation_id:
            query = query.where(LogEntry.correlation_id == wanted.correlation_id)
        return query

    async def lines(
        self, wanted: LogFilter, *, limit: int = 200, before: int | None = None, after: int | None = None
    ) -> list[LogEntry]:
        """Newest first; ``before`` pages back in time, ``after`` brings what came since (live)."""
        query = self._filtered(select(LogEntry), wanted)
        if before is not None:
            query = query.where(LogEntry.seq < before)
        if after is not None:
            query = query.where(LogEntry.seq > after)
        query = query.order_by(LogEntry.seq.desc()).limit(max(1, min(limit, 5_000)))
        async with self.database.session() as session:
            return list((await session.execute(query)).scalars())

    async def sources(self) -> list[str]:
        async with self.database.session() as session:
            rows = await session.execute(select(LogEntry.source).distinct().order_by(LogEntry.source))
            return [str(source) for source in rows.scalars()]

    async def viewed(self, actor: Principal, wanted: LogFilter, *, export: str | None = None) -> None:
        """The audit trail: every export, and the reading itself once per administrator every few minutes
        (the page follows the journal live: one entry per refresh would drown the trail)."""
        now = time.monotonic()
        if export is None and actor.user_id is not None:
            last = self._viewed.get(actor.user_id)
            if last is not None and now - last < VIEW_AUDIT_SECONDS:
                return
            self._viewed[actor.user_id] = now
        async with self.database.unit_of_work() as uow:
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action="observability.logs_exported" if export else "observability.logs_viewed",
                    actor=actor,
                    resource=ResourceRef("observability", "logs"),
                    decision="allow",
                    result="success",
                    context={**wanted.context(), **({"format": export} if export else {})},
                    sensitive=True,
                ),
            )
