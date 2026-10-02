"""Authentication routes (T025, T031): sign-in/out, registration, verification, ``GET /me``."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select

from portalab.core.authorization import public, require
from portalab.core.authz_port import Principal
from portalab.modules.identity.api.middleware import (
    SESSION_COOKIE,
    check_csrf,
    clear_session_cookies,
    identity_module,
    set_session_cookies,
)
from portalab.modules.identity.api.schemas import (
    Accepted,
    CredentialsConfirmation,
    LoginRequest,
    Me,
    OnboardingStep,
    RegisterRequest,
    SessionInfo,
    VerifyRequest,
)
from portalab.modules.identity.models import Profile, User
from portalab.modules.identity.module import IdentityModule
from portalab.modules.identity.services.common import UserNotFound, self_actor

router = APIRouter(prefix="/api/v1", tags=["identity"])
Module = Annotated[IdentityModule, Depends(identity_module)]

PROBLEMS: dict[int | str, dict[str, Any]] = {
    401: {"description": "auth.invalid_credentials"},
    403: {"description": "auth.account_unavailable"},
}


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post(
    "/auth/login", response_model=SessionInfo, responses={**PROBLEMS, 429: {"description": "auth.throttled"}}
)
@public
async def login(body: LoginRequest, request: Request, response: Response, module: Module) -> SessionInfo:
    signed_in = await module.auth.sign_in(
        body.login,
        body.password,
        client_ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
        previous_token=request.cookies.get(SESSION_COOKIE),
    )
    set_session_cookies(response, signed_in.issued, module.ctx.config.session_absolute_hours * 3600)
    return SessionInfo(
        user_id=signed_in.user_id,
        display_name=signed_in.display_name,
        csrf_token=signed_in.issued.csrf_token,
        expires_at=signed_in.issued.expires_at,
    )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
@public
async def logout(request: Request, module: Module) -> Response:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        check_csrf(request, token)
        await module.auth.sign_out(token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookies(response)
    return response


@router.post("/auth/register", status_code=status.HTTP_202_ACCEPTED, response_model=Accepted)
@public
async def register(body: RegisterRequest, module: Module) -> Accepted:
    await module.registration.register(
        login=body.login, display_name=body.display_name, password=body.password, email=body.email
    )
    return Accepted(detail="If the details are valid, the account now waits for verification.")


@router.post("/auth/verify", status_code=status.HTTP_204_NO_CONTENT)
@public
async def verify(body: VerifyRequest, module: Module) -> Response:
    await module.registration.verify(body.token, body.password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/auth/deletion/cancel", status_code=status.HTTP_204_NO_CONTENT, responses=PROBLEMS)
@public
async def cancel_deletion_with_credentials(
    body: CredentialsConfirmation, request: Request, module: Module
) -> Response:
    """Sign-in is refused during Pending Deletion, so the owner cancels by re-entering credentials."""
    user_id = await module.auth.verify_credentials(body.login, body.password, client_ip=client_ip(request))
    await module.deletion.cancel(self_actor(Principal(user_id=user_id)), user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=Me)
async def me(module: Module, principal: Principal = require("users.self.manage")) -> Me:
    assert principal.user_id is not None
    async with module.ctx.database.session() as session:
        user = await session.get(User, principal.user_id)
        if user is None:
            raise UserNotFound()
        has_avatar = bool(
            await session.scalar(select(Profile.avatar_blob_key).where(Profile.user_id == user.id))
        )
        progress = await module.onboarding.progress(session, user.id)
    return Me(
        id=user.id,
        login=user.login_display,
        display_name=user.display_name,
        email=user.email,
        state=user.state,
        created_at=user.created_at,
        verified_at=user.verified_at,
        has_avatar=has_avatar,
        onboarding=[OnboardingStep(step=item.step, completed_at=item.completed_at) for item in progress],
        deletion_due_at=user.deletion_due_at,
    )
