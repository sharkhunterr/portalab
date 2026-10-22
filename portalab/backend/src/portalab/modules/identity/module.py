"""Identity module facade: builds the services once and contributes routers, capabilities and jobs."""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.administration import BOOTSTRAP_CAPABILITY as BOOTSTRAP
from portalab.capabilities.administration import AdminSurface, default_admin_surfaces
from portalab.core.jobs.queue import enqueue
from portalab.core.jobs.registry import JobRegistry
from portalab.modules.identity import event_types as _event_types  # noqa: F401 — registers event types
from portalab.modules.identity.context import OWNER, IdentityContext
from portalab.modules.identity.jobs import dormancy, finalize_deletion, sessions_prune, verification_expiry
from portalab.modules.identity.search_provider import register_search
from portalab.modules.identity.services.account_service import AccountService
from portalab.modules.identity.services.admin_ops import AdminOperations
from portalab.modules.identity.services.auth import AuthService, LocalAuthProvider
from portalab.modules.identity.services.bootstrap import IdentityBootstrap
from portalab.modules.identity.services.credentials import CredentialHasher
from portalab.modules.identity.services.deletion import DeletionService
from portalab.modules.identity.services.directory import register_directory
from portalab.modules.identity.services.export import BUILD_JOB, EXPIRE_JOB, ExportService
from portalab.modules.identity.services.oidc import OidcService
from portalab.modules.identity.services.onboarding import OnboardingService
from portalab.modules.identity.services.participants import register_participants
from portalab.modules.identity.services.password import PasswordChangeService
from portalab.modules.identity.services.profile import AVATAR_GC_JOB, ProfileService, collect_avatar_blob
from portalab.modules.identity.services.registration import RegistrationService, VerificationChannel
from portalab.modules.identity.services.sessions import SessionService
from portalab.modules.identity.services.throttle import LoginThrottleService
from portalab.modules.identity.services.visibility import register_visibility

SWEEP_INTERVAL = timedelta(hours=1)
SWEEPS = (verification_expiry.KIND, dormancy.KIND, sessions_prune.KIND)


class IdentityModule:
    def __init__(self, ctx: IdentityContext, *, channel: VerificationChannel | None = None) -> None:
        self.ctx = ctx
        self.hasher = CredentialHasher(ctx.config.argon2_params)
        self.sessions = SessionService(lambda: ctx.config)
        self.throttle = LoginThrottleService()
        self.accounts = AccountService(ctx)
        self.onboarding = OnboardingService(ctx)
        self.auth = AuthService(
            ctx, LocalAuthProvider(self.hasher, ctx), self.sessions, self.throttle, self.accounts
        )
        self.oidc = OidcService(ctx, self.auth, self.accounts)  # 027: the single sign-on (Authentik)
        self.passwords = PasswordChangeService(ctx, self.auth, self.hasher, self.sessions)
        self.registration = RegistrationService(ctx, self.accounts, self.hasher, self.onboarding, channel)
        self.bootstrap = IdentityBootstrap(ctx, self.accounts, self.hasher, self.onboarding)
        self.admin = AdminOperations(ctx, self.accounts, self.sessions)
        self.profiles = ProfileService(ctx)
        self.deletion = DeletionService(ctx, self.accounts, self.sessions)
        self.exports = ExportService(ctx)

    # --- capabilities ----------------------------------------------------------------------------------
    def register_capabilities(self) -> None:
        register_directory(self.ctx.capabilities, self.ctx)
        register_participants(self.ctx.capabilities, self.ctx)
        register_visibility(self.ctx.capabilities, self.ctx)
        register_search(self.ctx)
        self.ctx.capabilities.provide(BOOTSTRAP, self.bootstrap, instance_ref="identity", owner=OWNER)
        default_admin_surfaces.register(
            AdminSurface("users", "admin.surface.users", "/admin/users", "users.manage", OWNER)
        )

    # --- jobs ----------------------------------------------------------------------------------------
    def register_jobs(self, registry: JobRegistry) -> None:
        async def finalize(payload: dict[str, Any]) -> None:
            await finalize_deletion.run(self.deletion, payload)

        async def build_export(payload: dict[str, Any]) -> None:
            await self.exports.build(UUID(str(payload["export_id"])))

        async def expire_export(payload: dict[str, Any]) -> None:
            await self.exports.expire(UUID(str(payload["export_id"])))

        async def avatar_gc(payload: dict[str, Any]) -> None:
            await collect_avatar_blob(self.ctx, str(payload["blob"]))

        async def expiry_sweep(payload: dict[str, Any]) -> None:
            await verification_expiry.run(self.ctx, self.deletion)
            await self._schedule_next(verification_expiry.KIND)

        async def dormancy_sweep(payload: dict[str, Any]) -> None:
            await dormancy.run(self.ctx, self.accounts)
            await self._schedule_next(dormancy.KIND)

        async def prune_sweep(payload: dict[str, Any]) -> None:
            await sessions_prune.run(self.ctx)
            await self._schedule_next(sessions_prune.KIND)

        handlers = (
            (
                finalize_deletion.KIND,
                finalize,
                "no-op once the request is cancelled/finalized; per-participant state",
            ),
            (BUILD_JOB, build_export, "no-op unless the export is still queued"),
            (EXPIRE_JOB, expire_export, "no-op once expired"),
            (AVATAR_GC_JOB, avatar_gc, "deleting an absent or re-referenced blob is a no-op"),
            (verification_expiry.KIND, expiry_sweep, "re-selects due accounts; guarded transitions"),
            (dormancy.KIND, dormancy_sweep, "re-checks activity under row lock"),
            (sessions_prune.KIND, prune_sweep, "deletes by cutoff; repeatable"),
        )
        for kind, handler, idempotency in handlers:
            registry.register(kind, handler, idempotency=idempotency, timeout_seconds=300, owner=OWNER)

    async def _schedule_next(self, kind: str) -> None:
        async with self.ctx.database.unit_of_work() as uow:
            await self.schedule_sweep(uow.session, kind, self.ctx.now() + SWEEP_INTERVAL)

    async def schedule_sweep(self, session: AsyncSession, kind: str, at: datetime) -> None:
        slot = at.replace(minute=0, second=0, microsecond=0)
        await enqueue(
            session,
            kind=kind,
            dedup_key=f"{kind}:{slot.strftime('%Y-%m-%dT%H')}",
            run_at=slot,
            clock=self.ctx.clock,
        )

    async def ensure_sweeps_scheduled(self) -> None:
        """Called at worker start: one pending run per sweep (deduplicated by hourly slot)."""
        async with self.ctx.database.unit_of_work() as uow:
            for kind in SWEEPS:
                await self.schedule_sweep(uow.session, kind, self.ctx.now())
