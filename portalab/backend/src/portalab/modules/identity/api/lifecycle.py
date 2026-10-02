"""Self-service lifecycle routes (T045): deletion request/cancel, personal-data export."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import StreamingResponse

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.modules.identity.api.auth import client_ip
from portalab.modules.identity.api.middleware import clear_session_cookies, identity_module
from portalab.modules.identity.api.schemas import DeletionStatus, ExportOut, PasswordConfirmation
from portalab.modules.identity.module import IdentityModule
from portalab.modules.identity.services.common import self_actor
from portalab.modules.identity.services.export import ExportStatus

router = APIRouter(prefix="/api/v1", tags=["identity"])
Module = Annotated[IdentityModule, Depends(identity_module)]


def _export(status_: ExportStatus) -> ExportOut:
    return ExportOut(
        id=status_.id,
        status=status_.status,
        requested_at=status_.requested_at,
        completed_at=status_.completed_at,
        expires_at=status_.expires_at,
    )


@router.post(
    "/me/deletion",
    response_model=DeletionStatus,
    responses={409: {"description": "admin.sole_admin_protected"}},
)
async def request_deletion(
    body: PasswordConfirmation,
    request: Request,
    response: Response,
    module: Module,
    principal: Principal = require("users.self.manage"),
) -> DeletionStatus:
    assert principal.user_id is not None
    await module.auth.reauthenticate(principal, body.password, client_ip=client_ip(request))
    deletion = await module.deletion.request(self_actor(principal), principal.user_id, reason="self_request")
    clear_session_cookies(response)  # every session was revoked with the request
    return DeletionStatus(state="pending_deletion", deletion_due_at=deletion.due_at)


@router.delete("/me/deletion", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_deletion(
    body: PasswordConfirmation,
    request: Request,
    module: Module,
    principal: Principal = require("users.self.manage"),
) -> Response:
    assert principal.user_id is not None
    await module.auth.reauthenticate(principal, body.password, client_ip=client_ip(request))
    await module.deletion.cancel(self_actor(principal), principal.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/export", status_code=status.HTTP_202_ACCEPTED, response_model=ExportOut)
async def request_export(module: Module, principal: Principal = require("users.self.manage")) -> ExportOut:
    return _export(await module.exports.request(principal))


@router.get("/me/export/{export_id}", response_model=ExportOut)
async def export_status(
    export_id: UUID, module: Module, principal: Principal = require("users.self.manage")
) -> ExportOut:
    return _export(await module.exports.get(principal, export_id))


@router.get(
    "/me/export/{export_id}/content",
    response_class=StreamingResponse,
    responses={200: {"content": {"application/json": {"schema": {"type": "string", "format": "binary"}}}}},
)
async def export_content(
    export_id: UUID, module: Module, principal: Principal = require("users.self.manage")
) -> StreamingResponse:
    stream = await module.exports.content(principal, export_id)
    return StreamingResponse(
        stream,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="portalab-export-{export_id}.json"',
            "Cache-Control": "no-store",
        },
    )
