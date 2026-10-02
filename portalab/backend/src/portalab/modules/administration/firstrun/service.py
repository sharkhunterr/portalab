"""First-run wizard (T022; R8, CD-032): validates the base settings, creates the sole Admin through the
``identity.bootstrap`` capability (the same service as ``portalab admin bootstrap``), runs registered optional
steps (e.g. ``services`` from spec 005, skippable), then locks itself (410). Reopening requires an explicit,
audited action by a holder of ``configuration.manage``."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.admin_authority import CAPABILITY as ADMIN_AUTHORITY
from portalab.capabilities.administration import BOOTSTRAP_CAPABILITY, FIRST_RUN_STEP_CAPABILITY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import PortalError, Unavailable, ValidationFailed
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock, utc_now
from portalab.modules.administration.config.service import Change, ConfigService
from portalab.modules.administration.models import FirstRun


class FirstRunClosed(PortalError):
    status = 410
    default_code = "admin.first_run_completed"
    default_title = "The first-run wizard is closed"


@dataclass(frozen=True, slots=True)
class WizardRequest:
    login: str
    password: str
    display_name: str | None = None
    email: str | None = None
    settings: Mapping[str, Any] = field(default_factory=dict)
    steps: Mapping[str, Any] = field(default_factory=dict)  # step id → payload, or None to skip


@dataclass(frozen=True, slots=True)
class WizardResult:
    admin_id: UUID
    steps: Mapping[str, str]


class FirstRunService:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        config: ConfigService,
        audit: AuditSink,
        events: EventPublisher,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.config = config
        self.audit = audit
        self.events = events
        self.clock = clock

    async def completed(self) -> bool:
        async with self.database.session() as session:
            return await session.scalar(select(FirstRun.completed_at).where(FirstRun.id == 1)) is not None

    def steps(self) -> list[dict[str, Any]]:
        return [
            {
                "step": reg.metadata.get("step", reg.instance_ref),
                "skippable": bool(reg.metadata.get("skippable", True)),
            }
            for reg in self.capabilities.system_providers(FIRST_RUN_STEP_CAPABILITY)
        ]

    async def admin_exists(self) -> bool:
        providers = self.capabilities.system_providers(ADMIN_AUTHORITY)
        if not providers:
            return False
        async with self.database.session() as session:
            return await providers[0].provider.current_admin(session) is not None

    async def run(self, request: WizardRequest, *, existing_admin: UUID | None = None) -> WizardResult:
        """Run the wizard; a reopened wizard (an Admin exists) runs as that Admin and creates no account."""
        if await self.completed():
            raise FirstRunClosed("The portal is already set up.")
        changes = [Change(key, value) for key, value in request.settings.items()]
        preview = await self.config.validate(changes)
        if not preview.ok:
            raise ValidationFailed(
                "Some settings are invalid.",
                code="admin.invalid_value",
                extensions={"errors": preview.errors},
            )
        if existing_admin is not None:
            admin_id = existing_admin
        else:
            bootstrappers = self.capabilities.system_providers(BOOTSTRAP_CAPABILITY)
            if not bootstrappers:
                raise Unavailable("Account creation is not available.", code="identity.unavailable")
            admin_id = await bootstrappers[0].provider.create_first_admin(
                login=request.login,
                password=request.password,
                display_name=request.display_name,
                email=request.email,
            )
        admin = Principal(user_id=admin_id)
        if changes:
            await self.config.apply(changes, admin, reason="first run")
        outcomes: dict[str, str] = {}
        for registration in self.capabilities.system_providers(FIRST_RUN_STEP_CAPABILITY):
            step = str(registration.metadata.get("step", registration.instance_ref))
            payload = request.steps.get(step)
            if payload is None:
                outcomes[step] = "skipped"
                continue
            try:
                await registration.provider.run(payload, admin_id)
                outcomes[step] = "done"
            except Exception:
                outcomes[step] = "failed"  # optional steps never block the setup; retried from the admin UI
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(FirstRun, 1, with_for_update=True)
            assert row is not None
            row.completed_at, row.completed_by = now, admin_id
            await self.events.publish(
                uow.session,
                "admin.firstrun_completed",
                {"steps": outcomes},
                occurred_at=now,
                actor=admin,
                source="administration",
                dedup_key="admin.firstrun_completed:1:" + now.strftime("%Y%m%dT%H%M%S"),
            )
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action="admin.firstrun_completed",
                    actor=admin,
                    context={"steps": outcomes},
                    sensitive=True,
                ),
            )
        return WizardResult(admin_id, outcomes)

    async def reopen(self, actor: Principal, reason: str) -> None:
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(FirstRun, 1, with_for_update=True)
            assert row is not None
            row.completed_at, row.completed_by = None, None
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action="admin.firstrun_reopened",
                    actor=actor,
                    context={"reason": reason[:256]},
                    sensitive=True,
                ),
            )
