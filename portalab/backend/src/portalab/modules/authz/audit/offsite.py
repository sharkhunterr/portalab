"""The audit trail copied off the machine as it is written (spec 030, FR-026, issue 144).

An administrator (or anyone who took the server) can do much on the machine itself; a copy kept elsewhere
— a JSON-lines file on a mounted remote volume, and/or a syslog server (RFC 5424 over TCP) — keeps what
happened out of their reach. The worker copies every new entry in ``seq`` order, without gaps, remembers
the last one copied (``<data dir>/audit-offsite.cursor``) and retries what could not be sent.
"""

import asyncio
import json
import os
import socket
from pathlib import Path
from typing import Any

from sqlalchemy import select

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog
from portalab.core.db import Database
from portalab.core.logging import get_logger
from portalab.modules.authz.models import AuditEntry

log = get_logger("portalab.audit.offsite")
OWNER = "module:authz"
FILE_KEY = "audit.offsite.file"
SYSLOG_KEY = "audit.offsite.syslog"
BATCH = 500


def declare_offsite_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {d.key for d in catalog.all()}
    for key, description in (
        (
            FILE_KEY,
            "A file (on a volume mounted from elsewhere) the audit trail is copied to, as JSON lines.",
        ),
        (SYSLOG_KEY, "A syslog server (host:port, TCP) the audit trail is sent to, as it is written."),
    ):
        if key not in known:
            declare(scope="global", key=key, schema=str, default="", owner=OWNER, description=description)


declare_offsite_settings()


def record(entry: AuditEntry) -> dict[str, Any]:
    return {
        "seq": entry.seq,
        "occurred_at": entry.occurred_at.isoformat(),
        "actor_user_id": str(entry.actor_user_id) if entry.actor_user_id else None,
        "actor_kind": entry.actor_kind,
        "acting_for": str(entry.acting_for) if entry.acting_for else None,
        "action": entry.action,
        "resource_type": entry.resource_type,
        "resource_id": entry.resource_id,
        "decision": entry.decision,
        "result": entry.result,
        "context": entry.context,
        "correlation_id": entry.correlation_id,
    }


def syslog_line(item: dict[str, Any], hostname: str) -> bytes:
    """RFC 5424 (facility local0, notice), octet-counted framing (RFC 6587)."""
    message = json.dumps(item, separators=(",", ":"), default=str)
    line = f"<133>1 {item['occurred_at']} {hostname} portalab - audit - {message}".encode()
    return str(len(line)).encode() + b" " + line


class AuditCopier:
    def __init__(self, database: Database, data_dir: Path) -> None:
        self.database = database
        self.cursor_path = data_dir / "audit-offsite.cursor"

    def _cursor(self) -> int:
        try:
            return int(self.cursor_path.read_text().strip() or 0)
        except (OSError, ValueError):
            return 0

    def _save(self, seq: int) -> None:
        temporary = self.cursor_path.with_suffix(".tmp")
        temporary.write_text(str(seq))
        temporary.replace(self.cursor_path)

    async def run_once(self, *, file: str = "", syslog: str = "") -> int:
        """Copy what is new to the sinks configured; returns how many entries were copied."""
        if not file and not syslog:
            return 0
        after = self._cursor()
        async with self.database.session() as session:
            entries = list(
                (
                    await session.execute(
                        select(AuditEntry).where(AuditEntry.seq > after).order_by(AuditEntry.seq).limit(BATCH)
                    )
                ).scalars()
            )
        if not entries:
            return 0
        items = [record(e) for e in entries]
        if file:
            await asyncio.to_thread(self._append, Path(file), items)
        if syslog:
            await self._send(syslog, items)
        self._save(int(entries[-1].seq))
        return len(entries)

    @staticmethod
    def _append(path: Path, items: list[dict[str, Any]]) -> None:
        with path.open("a", encoding="utf-8") as handle:
            for item in items:
                handle.write(json.dumps(item, separators=(",", ":"), default=str) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    async def _send(target: str, items: list[dict[str, Any]]) -> None:
        host, _, port = target.rpartition(":")
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, int(port)), timeout=5)
        try:
            name = socket.gethostname()[:64] or "portalab"
            for item in items:
                writer.write(syslog_line(item, name))
            await asyncio.wait_for(writer.drain(), timeout=10)
        finally:
            writer.close()
            reader.feed_eof()
