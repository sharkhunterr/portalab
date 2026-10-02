"""Sync API (T025, T030): manual sync, resync (full = sensitive + confirmation), run history."""

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from portalab.capabilities.confirmations import CAPABILITY as CONFIRMATIONS
from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import Conflict, Forbidden, Unavailable
from portalab.modules.connectors.api.services import Module
from portalab.modules.connectors.models import SyncRun, SyncState
from portalab.modules.connectors.permissions import SERVICES_MANAGE, SERVICES_READ
from portalab.modules.connectors.services.common import ServiceDisabled, SyncInProgress, service_ref

router = APIRouter(prefix="/api/v1", tags=["connectors"])
RESYNC_FULL = "services.manage"


class ConfirmationRequired(Conflict):
    default_code = "authz.confirmation_required"
    default_title = "Confirmation required"


class ResyncIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["partial", "full"]
    allow_large_deletion: bool = False
    confirmation: str | None = Field(default=None, max_length=128)


def _run(row: SyncRun) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "kind": row.kind,
        "capability": row.capability,
        "status": row.status,
        "started_at": row.started_at.isoformat(),
        "finished_at": row.finished_at.isoformat(),
        "added": row.added,
        "modified": row.modified,
        "removed": row.removed,
        "ignored": row.ignored,
        "errored": row.errored,
        "partial": row.partial,
        "last_error": row.last_error,
    }


@router.post("/services/{service_id}/sync", status_code=status.HTTP_202_ACCEPTED)
async def sync_now(
    principal: Annotated[Principal, require(SERVICES_MANAGE)], service_id: UUID, module: Module
) -> dict[str, Any]:
    async with module.database.unit_of_work() as uow:
        row = await module.manager._row(uow.session, service_id)
        if row.state not in ("enabled", "error", "unavailable"):
            raise ServiceDisabled("This service is not enabled; it cannot be synchronized.")
        state = await uow.session.get(SyncState, service_id)
        if state is not None and state.status == "running":
            raise SyncInProgress("A synchronization of this service is already running.")
        result = await module.scheduler.enqueue(
            uow.session, service_id, kind="manual", requested_by=principal.user_id
        )
    return {"job_id": str(result.job_id), "queued": result.created}


@router.post(
    "/services/{service_id}/resync",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        409: {"description": "authz.confirmation_required (carries `confirmation`) for a full resync"}
    },
)
async def resync(
    principal: Annotated[Principal, require(SERVICES_MANAGE)],
    service_id: UUID,
    body: ResyncIn,
    module: Module,
) -> dict[str, Any]:
    if body.mode == "full":
        providers = module.capabilities.system_providers(CONFIRMATIONS)
        if not providers:
            raise Unavailable("Confirmations are not available.", code="authz.unavailable")
        confirmations = providers[0].provider
        resource = service_ref(service_id)
        payload = {"mode": "full", "allow_large_deletion": body.allow_large_deletion}
        if body.confirmation is None:
            issued = await confirmations.issue(principal, RESYNC_FULL, resource, payload)
            raise ConfirmationRequired(
                "A full resync deactivates this service's records the source no longer lists. "
                "Confirm to continue.",
                extensions={"confirmation": issued},
            )
        if not await confirmations.consume(body.confirmation, principal, RESYNC_FULL, resource, payload):
            raise Forbidden("The confirmation is invalid or expired.", code="authz.confirmation_invalid")
    result = await module.resync.request(
        principal, service_id, body.mode, allow_large_deletion=body.allow_large_deletion
    )
    return {"job_id": str(result.job_id), "queued": result.created}


@router.get("/services/{service_id}/sync-runs")
async def sync_runs(
    _: Annotated[Principal, require(SERVICES_READ)],
    service_id: UUID,
    module: Module,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    await module.manager.get(service_id)
    async with module.database.session() as session:
        rows = (
            await session.execute(
                select(SyncRun)
                .where(SyncRun.service_id == service_id)
                .order_by(SyncRun.started_at.desc(), SyncRun.id.desc())
                .limit(limit)
            )
        ).scalars()
        return {"items": [_run(row) for row in rows]}
