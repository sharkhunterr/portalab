"""Administrative account routes (T035, T047; CD-036 account creation by the Admin)."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.modules.identity.api.auth import client_ip
from portalab.modules.identity.api.middleware import identity_module
from portalab.modules.identity.api.schemas import (
    AdminCreateUser,
    AdminReason,
    AdminTransferRequest,
    DeletionStatus,
    UserList,
    UserListItem,
    VerificationTokenOut,
)
from portalab.modules.identity.models import STATES
from portalab.modules.identity.module import IdentityModule
from portalab.modules.identity.services.common import admin_actor

router = APIRouter(prefix="/api/v1", tags=["identity-admin"])
Module = Annotated[IdentityModule, Depends(identity_module)]
SOLE_ADMIN: dict[int | str, dict[str, Any]] = {409: {"description": "admin.sole_admin_protected"}}


@router.get("/users", response_model=UserList)
async def list_users(
    module: Module,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
    state: Annotated[str | None, Query(pattern="^(" + "|".join(STATES) + ")$")] = None,
    principal: Principal = require("users.manage"),
) -> UserList:
    page = await module.admin.list_users(limit=limit, cursor=cursor, state=state)
    return UserList(
        items=[
            UserListItem(
                id=row.id,
                login=row.login,
                display_name=row.display_name,
                state=row.state,
                created_at=row.created_at,
                last_sign_in_at=row.last_sign_in_at,
            )
            for row in page.items
        ],
        next_cursor=page.next_cursor,
    )


@router.post("/users", status_code=status.HTTP_201_CREATED, response_model=VerificationTokenOut)
async def create_user(
    body: AdminCreateUser, module: Module, principal: Principal = require("users.manage")
) -> VerificationTokenOut:
    issued = await module.registration.admin_create(
        principal, login=body.login, display_name=body.display_name, email=body.email
    )
    return VerificationTokenOut(
        user_id=issued.user_id, verification_token=issued.token, expires_at=issued.expires_at
    )


@router.post("/users/{user_id}/verification", response_model=VerificationTokenOut)
async def reissue_verification(
    user_id: UUID, module: Module, principal: Principal = require("users.manage")
) -> VerificationTokenOut:
    issued = await module.registration.reissue(principal, user_id)
    return VerificationTokenOut(
        user_id=issued.user_id, verification_token=issued.token, expires_at=issued.expires_at
    )


@router.post("/users/{user_id}/suspend", status_code=status.HTTP_204_NO_CONTENT, responses=SOLE_ADMIN)
async def suspend_user(
    user_id: UUID, body: AdminReason, module: Module, principal: Principal = require("users.manage")
) -> Response:
    await module.admin.suspend(principal, user_id, body.reason)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/users/{user_id}/reactivate", status_code=status.HTTP_204_NO_CONTENT)
async def reactivate_user(
    user_id: UUID, body: AdminReason, module: Module, principal: Principal = require("users.manage")
) -> Response:
    await module.admin.reactivate(principal, user_id, body.reason)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/users/{user_id}/deletion", response_model=DeletionStatus, responses=SOLE_ADMIN)
async def request_user_deletion(
    user_id: UUID, body: AdminReason, module: Module, principal: Principal = require("users.manage")
) -> DeletionStatus:
    request = await module.deletion.request(admin_actor(principal), user_id, reason=body.reason)
    return DeletionStatus(state="pending_deletion", deletion_due_at=request.due_at)


@router.delete("/users/{user_id}/deletion", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_user_deletion(
    user_id: UUID, module: Module, principal: Principal = require("users.manage")
) -> Response:
    await module.deletion.cancel(admin_actor(principal), user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/admin/transfer", status_code=status.HTTP_204_NO_CONTENT, responses=SOLE_ADMIN)
async def transfer_admin(
    body: AdminTransferRequest,
    request: Request,
    module: Module,
    principal: Principal = require("users.admin.transfer"),
) -> Response:
    await module.auth.reauthenticate(principal, body.password, client_ip=client_ip(request))
    await module.admin.transfer_admin(principal, body.target_user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
