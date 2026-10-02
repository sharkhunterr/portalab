"""Personal-data export (T045; FR-018/019, SC-005).

A request creates an ``export_jobs`` row and a ``build_export`` job; the builder asks every registered
``privacy.export_contributor`` for the user's records, refuses any secret-looking key (credentials, tokens),
stores one JSON bundle in the blob store and schedules its deletion at ``expires_at``. Only the requester can
read the job or download the bundle.
"""

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.privacy_participants import EXPORT_CAPABILITY
from portalab.core.authz_port import Principal
from portalab.core.errors import NotFound
from portalab.core.jobs.queue import check_payload, enqueue
from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.models import ExportJob
from portalab.modules.identity.services.common import SYSTEM, audit, publish, user_ref

BUILD_JOB = "identity.build_export"
EXPIRE_JOB = "identity.expire_export"
NAMESPACE = "exports"
FORMAT = "portalab.personal-data-export"


@dataclass(frozen=True, slots=True)
class ExportStatus:
    id: UUID
    status: str
    requested_at: datetime
    completed_at: datetime | None
    expires_at: datetime | None


def _status(job: ExportJob) -> ExportStatus:
    return ExportStatus(job.id, job.status, job.requested_at, job.completed_at, job.expires_at)


class ExportService:
    def __init__(self, ctx: IdentityContext) -> None:
        self.ctx = ctx

    async def request(self, principal: Principal) -> ExportStatus:
        assert principal.user_id is not None
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            job = ExportJob(user_id=principal.user_id, requested_at=now, status="queued")
            uow.session.add(job)
            await uow.session.flush()
            await enqueue(
                uow.session,
                kind=BUILD_JOB,
                payload={"export_id": str(job.id)},
                dedup_key=f"{BUILD_JOB}:{job.id}",
                clock=self.ctx.clock,
            )
            await publish(
                self.ctx,
                uow.session,
                "user.data_export_requested",
                principal.user_id,
                actor=principal,
                occurred_at=now,
                metadata={"export_id": str(job.id)},
                dedup_key=f"export:{job.id}:requested",
            )
            await audit(
                self.ctx,
                uow.session,
                "user.data_export_requested",
                principal,
                resource=user_ref(principal.user_id),
                context={"export_id": str(job.id)},
                sensitive=True,
            )
            return _status(job)

    async def get(self, principal: Principal, export_id: UUID) -> ExportStatus:
        return _status(await self._owned(principal, export_id))

    async def _owned(self, principal: Principal, export_id: UUID) -> ExportJob:
        async with self.ctx.database.session() as session:
            job = await session.get(ExportJob, export_id)
        if job is None or job.user_id != principal.user_id:
            raise NotFound()  # never reveal other users' exports
        return job

    async def content(self, principal: Principal, export_id: UUID) -> AsyncIterator[bytes]:
        job = await self._owned(principal, export_id)
        if (
            job.status != "ready"
            or job.blob_key is None
            or (job.expires_at and job.expires_at <= self.ctx.now())
        ):
            raise NotFound("This export is not available.")
        return self.ctx.blobs.stream(job.blob_key)

    async def build(self, export_id: UUID) -> None:
        async with self.ctx.database.session() as session:
            job = await session.get(ExportJob, export_id)
        if job is None or job.status != "queued":
            return  # duplicate delivery or already built
        sections: list[dict[str, Any]] = []
        for registration in self.ctx.capabilities.system_providers(EXPORT_CAPABILITY):
            records = await registration.provider.export(job.user_id)
            section = {
                "contributor": registration.instance_ref,
                "records": [{"category": record.category, "data": dict(record.data)} for record in records],
            }
            check_payload(section)  # a contributor leaking a secret-looking key fails the export
            sections.append(section)
        now = self.ctx.now()
        bundle = {
            "format": FORMAT,
            "version": 1,
            "generated_at": now.isoformat(),
            "subject": str(job.user_id),
            "sections": sections,
        }
        data = json.dumps(bundle, default=str, ensure_ascii=False, indent=2).encode("utf-8")
        blob = await self.ctx.blobs.put(NAMESPACE, data, content_type="application/json")
        expires_at = now + timedelta(hours=self.ctx.config.export_ttl_hours)
        async with self.ctx.database.unit_of_work() as uow:
            current = await uow.session.get(ExportJob, export_id, with_for_update=True)
            if current is None or current.status != "queued":
                return
            current.status = "ready"
            current.blob_key = blob.key
            current.completed_at = now
            current.expires_at = expires_at
            await enqueue(
                uow.session,
                kind=EXPIRE_JOB,
                payload={"export_id": str(export_id)},
                dedup_key=f"{EXPIRE_JOB}:{export_id}",
                run_at=expires_at,
                clock=self.ctx.clock,
            )
            await publish(
                self.ctx,
                uow.session,
                "user.data_exported",
                job.user_id,
                actor=SYSTEM.principal,
                occurred_at=now,
                metadata={"export_id": str(export_id)},
                dedup_key=f"export:{export_id}:ready",
            )

    async def expire(self, export_id: UUID) -> None:
        async with self.ctx.database.unit_of_work() as uow:
            job = await uow.session.get(ExportJob, export_id, with_for_update=True)
            if job is None or job.status == "expired":
                return
            key = job.blob_key
            job.status = "expired"
            job.blob_key = None
        if key is not None:
            await self.ctx.blobs.delete(key)

    async def delete_all_for(self, user_id: UUID) -> None:
        async with self.ctx.database.unit_of_work() as uow:
            jobs = list(
                (await uow.session.execute(select(ExportJob).where(ExportJob.user_id == user_id))).scalars()
            )
            keys = [job.blob_key for job in jobs if job.blob_key]
            for job in jobs:
                await uow.session.delete(job)
        for key in keys:
            await self.ctx.blobs.delete(key)
