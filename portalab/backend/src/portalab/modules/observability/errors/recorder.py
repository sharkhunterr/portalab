"""Structured error recorder (T010; R3, FR-015/016/031).

Errors arrive from the kernel hook (``default_metrics.error``). Each is identified by a **fingerprint** of
its component, category, exception type and *normalized* message (ids, numbers, hosts, quoted values and
emails removed), so 50 occurrences of the same failure are one row with ``count = 50`` and first/last
seen. Messages and contexts are redacted again here (secrets, tokens, emails) and personal data is reduced
to an optional user id. A resolved error that happens again is reopened (regression).
"""

import hashlib
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.authz_port import Principal
from portalab.core.errors import NotFound, ValidationFailed
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.logging import redact, redact_text
from portalab.modules.observability.models import ErrorRecord

_VOLATILE: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+"), "<email>"),
    (
        re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE),
        "<uuid>",
    ),
    (re.compile(r"[a-z][a-z0-9+.\-]*://\S+", re.IGNORECASE), "<url>"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b"), "<ip>"),
    (re.compile(r"\b[0-9a-f]{12,}\b", re.IGNORECASE), "<hex>"),
    (re.compile(r"(['\"]).*?\1"), "<value>"),
    (re.compile(r"\d+(\.\d+)?"), "<n>"),
)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")


class ErrorNotFound(NotFound):
    default_code = "observability.error_not_found"


def normalize(message: str) -> str:
    text = message
    for pattern, replacement in _VOLATILE:
        text = pattern.sub(replacement, text)
    return re.sub(r"\s+", " ", text).strip()[:500]


def fingerprint(component: str, category: str, error_type: str, message: str) -> str:
    basis = "|".join((component, category, error_type, normalize(message)))
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def clean_message(message: str) -> str:
    return _EMAIL.sub("<email>", redact_text(message))[:2000]


def _uuid(value: Any) -> UUID | None:
    try:
        return UUID(str(value)) if value else None
    except ValueError:
        return None


class ErrorRecorder:
    def __init__(self, events: EventPublisher) -> None:
        self.events = events

    async def record(
        self, session: AsyncSession, component: str, error: Mapping[str, Any], at: datetime, count: int = 1
    ) -> bool:
        """Upsert one fingerprint; returns True on the first occurrence (or a reopened regression)."""
        category = str(error.get("category") or "")
        if not component or not category:
            raise ValidationFailed("An error record needs a component and a category.")
        error_type = str(error.get("type") or "error")[:128]
        message = clean_message(str(error.get("message") or ""))
        context = redact(dict(error.get("context") or {}))
        context = {
            str(k): (_EMAIL.sub("<email>", v) if isinstance(v, str) else v) for k, v in context.items()
        }
        key = fingerprint(component, category, error_type, message)
        existing = (
            await session.execute(select(ErrorRecord).where(ErrorRecord.fingerprint == key).with_for_update())
        ).scalar_one_or_none()
        if existing is not None:
            reopened = existing.state == "resolved"
            existing.count += count
            existing.last_seen_at = max(existing.last_seen_at, at)
            existing.message, existing.context = message, context
            if reopened:
                existing.state, existing.resolution, existing.resolved_by, existing.resolved_at = (
                    "open",
                    None,
                    None,
                    None,
                )
                await self._publish(session, existing, "reopened", at)
            return reopened
        await session.execute(
            insert(ErrorRecord)
            .values(
                fingerprint=key,
                component=component[:128],
                service_ref=(str(error["service_ref"])[:64] if error.get("service_ref") else None),
                plugin_ref=(str(error["plugin_ref"])[:128] if error.get("plugin_ref") else None),
                event_ref=(str(error["event_ref"])[:64] if error.get("event_ref") else None),
                user_ref=_uuid(error.get("user_ref")),
                category=category[:64],
                error_type=error_type,
                level=str(error.get("level") or "error")[:16],
                message=message,
                context=context,
                count=count,
                first_seen_at=at,
                last_seen_at=at,
                state="open",
            )
            .on_conflict_do_update(
                constraint="uq_errors_fingerprint",
                set_={"count": ErrorRecord.count + count, "last_seen_at": at},
            )
        )
        row = (await session.execute(select(ErrorRecord).where(ErrorRecord.fingerprint == key))).scalar_one()
        await self._publish(session, row, "recorded", at)
        return True

    async def _publish(self, session: AsyncSession, row: ErrorRecord, change: str, at: datetime) -> None:
        await self.events.publish(
            session,
            "observability.error_recorded",
            {"error_id": str(row.id), "component": row.component, "category": row.category, "change": change},
            occurred_at=at,
            subject=SubjectRef("observability_error", str(row.id)),
            source="observability",
        )

    async def transition(
        self,
        session: AsyncSession,
        error_id: UUID,
        actor: Principal,
        to: str,
        resolution: str | None,
        at: datetime,
    ) -> ErrorRecord:
        row = await session.get(ErrorRecord, error_id, with_for_update=True)
        if row is None:
            raise ErrorNotFound("No such error.")
        if to == "resolved":
            if not resolution or not resolution.strip():
                raise ValidationFailed(
                    "Resolving an error needs a resolution note.", code="observability.resolution_required"
                )
            row.state, row.resolution, row.resolved_by, row.resolved_at = (
                "resolved",
                redact_text(resolution.strip())[:2000],
                actor.user_id,
                at,
            )
        else:
            row.state = "acknowledged"
        await self._publish(session, row, to, at)
        return row
