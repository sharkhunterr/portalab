"""Profile routes (T039): own profile and avatar, other members' profiles (visibility-filtered),
onboarding progress."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import StreamingResponse

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.modules.identity.api.middleware import identity_module
from portalab.modules.identity.api.schemas import OnboardingStep, ProfileFieldOut, ProfileOut, ProfilePatch
from portalab.modules.identity.module import IdentityModule
from portalab.modules.identity.services.avatar import MAX_BYTES, InvalidAvatar
from portalab.modules.identity.services.profile import FieldUpdate, ProfileView

router = APIRouter(prefix="/api/v1", tags=["identity"])
Module = Annotated[IdentityModule, Depends(identity_module)]


def _out(view: ProfileView) -> ProfileOut:
    return ProfileOut(
        user_id=view.user_id,
        display_name=view.display_name,
        has_avatar=view.has_avatar,
        fields=[ProfileFieldOut(key=f.key, value=f.value, visibility=f.visibility) for f in view.fields],
    )


@router.patch(
    "/me/profile", response_model=ProfileOut, responses={409: {"description": "user.display_name_taken"}}
)
async def update_profile(
    body: ProfilePatch, module: Module, principal: Principal = require("users.self.manage")
) -> ProfileOut:
    fields = (
        {key: FieldUpdate(value=item.value, visibility=item.visibility) for key, item in body.fields.items()}
        if body.fields is not None
        else None
    )
    view = await module.profiles.update(principal, display_name=body.display_name, fields=fields)
    return _out(view)


@router.put(
    "/me/avatar",
    status_code=status.HTTP_204_NO_CONTENT,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                t: {"schema": {"type": "string", "format": "binary"}}
                for t in ("image/png", "image/jpeg", "image/webp", "image/gif")
            },
        }
    },
)
async def put_avatar(
    request: Request, module: Module, principal: Principal = require("users.self.manage")
) -> Response:
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > MAX_BYTES:
            raise InvalidAvatar("The image is larger than 2 MiB.", extensions={"reason": "too_large"})
    await module.profiles.set_avatar(principal, bytes(data))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/me/avatar", status_code=status.HTTP_204_NO_CONTENT)
async def delete_avatar(module: Module, principal: Principal = require("users.self.manage")) -> Response:
    await module.profiles.remove_avatar(principal)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users/{user_id}/profile", response_model=ProfileOut)
async def user_profile(
    user_id: UUID, module: Module, principal: Principal = require("users.read")
) -> ProfileOut:
    return _out(await module.profiles.view(principal, user_id))


@router.get(
    "/users/{user_id}/avatar",
    response_class=StreamingResponse,
    responses={200: {"content": {"image/png": {"schema": {"type": "string", "format": "binary"}}}}},
)
async def user_avatar(
    user_id: UUID, module: Module, principal: Principal = require("users.read")
) -> StreamingResponse:
    key, content_type = await module.profiles.avatar(user_id)
    return StreamingResponse(
        module.ctx.blobs.stream(key),
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/me/onboarding", response_model=list[OnboardingStep])
async def onboarding(
    module: Module, principal: Principal = require("users.self.manage")
) -> list[OnboardingStep]:
    assert principal.user_id is not None
    async with module.ctx.database.session() as session:
        progress = await module.onboarding.progress(session, principal.user_id)
    return [OnboardingStep(step=item.step, completed_at=item.completed_at) for item in progress]


@router.post("/me/onboarding/{step}/complete", response_model=list[OnboardingStep])
async def complete_onboarding_step(
    step: str, module: Module, principal: Principal = require("users.self.manage")
) -> list[OnboardingStep]:
    progress = await module.onboarding.complete(principal, step)
    return [OnboardingStep(step=item.step, completed_at=item.completed_at) for item in progress]
