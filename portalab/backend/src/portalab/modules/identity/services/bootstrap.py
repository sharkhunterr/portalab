"""``IdentityBootstrap`` — creation of the first and only Admin (research R13, OQ-6 default).

Used by the CLI ``portalab admin bootstrap`` and later by the Administration first-run wizard (020): one
code path. A transaction-scoped advisory lock serializes concurrent bootstraps; the authorization module's
``grant_first_admin`` refuses when an Admin exists, so exactly one call can ever win.
"""

from uuid import UUID

from sqlalchemy import text

from portalab.capabilities.admin_authority import AdminAlreadyExists
from portalab.core.errors import Conflict
from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.domain.state_machine import AccountState
from portalab.modules.identity.services.account_service import AccountService, LoginTaken
from portalab.modules.identity.services.common import SYSTEM, audit, user_ref
from portalab.modules.identity.services.credentials import (
    CredentialHasher,
    check_password_policy,
    set_password,
)
from portalab.modules.identity.services.onboarding import OnboardingService

_LOCK_SQL = text("SELECT pg_advisory_xact_lock(hashtext('portalab.identity.bootstrap'))")


class AdminExists(Conflict):
    default_code = "admin.already_exists"
    default_title = "An Admin already exists"

    def __init__(self) -> None:
        super().__init__("The portal already has its Admin; use an Admin transfer instead.")


class IdentityBootstrap:
    def __init__(
        self,
        ctx: IdentityContext,
        accounts: AccountService,
        hasher: CredentialHasher,
        onboarding: OnboardingService,
    ) -> None:
        self.ctx = ctx
        self.accounts = accounts
        self.hasher = hasher
        self.onboarding = onboarding

    async def create_first_admin(
        self, *, login: str, password: str, display_name: str | None = None, email: str | None = None
    ) -> UUID:
        check_password_policy(password, self.ctx.config.password_policy, personal=(login, display_name or ""))
        authority = self.ctx.admin_authority()
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            await uow.session.execute(_LOCK_SQL)
            if await authority.current_admin(uow.session) is not None:
                raise AdminExists()
            try:
                user = await self.accounts.create_user(
                    uow.session,
                    login=login,
                    display_name=display_name or login,
                    email=email,
                    state=AccountState.ACTIVE,
                    actor=SYSTEM,
                    reason="bootstrap",
                )
            except LoginTaken as exc:
                raise Conflict("This login is already in use.", code="user.login_taken") from exc
            await set_password(uow.session, self.hasher, user.id, password, now)
            try:
                await authority.grant_first_admin(uow.session, user.id)
            except AdminAlreadyExists as exc:
                raise AdminExists() from exc
            await self.onboarding.start(uow.session, user.id, now)
            await audit(
                self.ctx,
                uow.session,
                "admin.bootstrapped",
                SYSTEM.principal,
                resource=user_ref(user.id),
                sensitive=True,
            )
            return user.id
