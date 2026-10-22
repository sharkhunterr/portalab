"""A member changes their own password: the current one first (the same throttled check as the sign-in),
then the new one against the password policy; their other sessions are signed out, this one stays.

An account without a local password (signed in through the single sign-on) has none to change: its
password lives with that provider."""

from uuid import UUID

from sqlalchemy import select

from portalab.core.authz_port import Principal
from portalab.core.errors import Conflict, Forbidden, ValidationFailed
from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.models import Credential, User
from portalab.modules.identity.services.auth import AuthService
from portalab.modules.identity.services.common import InvalidCredentials, audit, user_ref
from portalab.modules.identity.services.credentials import (
    CredentialHasher,
    check_password_policy,
    set_password,
)
from portalab.modules.identity.services.sessions import SessionService


class PasswordChangeService:
    def __init__(
        self, ctx: IdentityContext, auth: AuthService, hasher: CredentialHasher, sessions: SessionService
    ) -> None:
        self.ctx = ctx
        self.auth = auth
        self.hasher = hasher
        self.sessions = sessions

    async def change(self, principal: Principal, current: str, new: str, *, client_ip: str | None) -> int:
        """Returns how many other sessions were signed out."""
        if principal.user_id is None or principal.acting_for is not None:
            raise Forbidden("Only the member themselves may change their password.")
        user_id: UUID = principal.user_id
        async with self.ctx.database.session() as session:
            row = (
                await session.execute(
                    select(User.login, Credential.user_id)
                    .join(Credential, Credential.user_id == User.id, isouter=True)
                    .where(User.id == user_id)
                )
            ).one_or_none()
        if row is None or row.user_id is None:
            raise Conflict(
                "This account has no password of its own: it signs in through the single sign-on.",
                code="identity.password_not_local",
            )
        try:
            checked = await self.auth.verify_credentials(row.login, current, client_ip=client_ip)
        except InvalidCredentials:
            # never a 401 for a signed-in member: the page would take it for an ended session
            raise ValidationFailed(
                "The current password is not right.", code="identity.password_current_wrong"
            ) from None
        if checked != user_id:
            raise ValidationFailed(
                "The current password is not right.", code="identity.password_current_wrong"
            )
        if new == current:
            raise ValidationFailed(
                "Choose a password different from the current one.", code="identity.password_unchanged"
            )
        check_password_policy(new, self.ctx.config.password_policy)
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            await set_password(uow.session, self.hasher, user_id, new, now)
            signed_out = await self.sessions.revoke_all(
                uow.session, user_id, now, "password_change", except_id=principal.session_id
            )
            await audit(
                self.ctx,
                uow.session,
                "identity.password_changed",
                principal,
                resource=user_ref(user_id),
                context={"other_sessions_signed_out": signed_out},
                sensitive=True,
            )
        return signed_out
