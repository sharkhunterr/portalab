"""Live notifications outbox ``core.live_event`` feeding the SSE stream.

See plan §6 and api-conventions "Live updates".

Live events are *notifications to refetch or small deltas*, never a source of truth: the domain event model
and history belong to spec 007. Producers call :func:`publish_live` inside their own transaction (outbox
pattern), so a notification is visible only if the state change committed. Each row carries the visibility
rule used to filter it per subscriber: an audience user and/or a permission (+ resource) checked through the
Authorizer port.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, Identity, String, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from portalab.core.authz_port import ResourceRef
from portalab.core.db import CoreBase, TZDateTime
from portalab.core.jobs.queue import check_payload
from portalab.core.privacy_registry import pii
from portalab.core.time import Clock, utc_now


class LiveEvent(CoreBase):
    __tablename__ = "live_event"

    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    topic: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    permission: Mapped[str | None] = mapped_column(String(128))
    resource_kind: Mapped[str | None] = mapped_column(String(64))
    resource_id: Mapped[str | None] = mapped_column(String(128))
    audience_user_id: Mapped[UUID | None] = mapped_column(info=pii("identifier"))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, index=True)

    @property
    def resource(self) -> ResourceRef | None:
        if self.resource_kind is None:
            return None
        return ResourceRef(kind=self.resource_kind, id=self.resource_id)


async def publish_live(
    session: AsyncSession,
    *,
    topic: str,
    payload: dict[str, Any] | None = None,
    permission: str | None = None,
    resource: ResourceRef | None = None,
    audience_user_id: UUID | None = None,
    clock: Clock | None = None,
) -> int:
    """Queue a live notification in the caller's transaction; returns its sequence number."""
    payload = dict(payload or {})
    check_payload(payload)
    event = LiveEvent(
        topic=topic,
        payload=payload,
        permission=permission,
        resource_kind=resource.kind if resource else None,
        resource_id=resource.id if resource else None,
        audience_user_id=audience_user_id,
        created_at=utc_now(clock),
    )
    session.add(event)
    await session.flush()
    return int(event.seq)


async def fetch_after(session: AsyncSession, after_seq: int, limit: int) -> list[LiveEvent]:
    statement = select(LiveEvent).where(LiveEvent.seq > after_seq).order_by(LiveEvent.seq).limit(limit)
    return list((await session.execute(statement)).scalars())


async def latest_seq(session: AsyncSession) -> int:
    value = (await session.execute(select(LiveEvent.seq).order_by(LiveEvent.seq.desc()).limit(1))).scalar()
    return int(value or 0)
