"""``authz.admin_authority`` (T025; R5, FR-009..012, CD-001).

Exactly one Admin, never zero, never two: the one-row ``authz.admin_singleton`` is locked ``FOR UPDATE`` by
every change, and a partial unique index allows at most one active Admin assignment. There is no delegation
and no time-boxed Admin; revoking the Admin is only possible inside :meth:`transfer_admin`. Every attempt —
successful or refused — emits ``permission.admin_transfer_attempted`` and an audit entry.
"""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.admin_authority import CAPABILITY, AdminAlreadyExists, AdminTransferRefused
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.authz.models import ADMIN_ROLE_ID, AdminSingleton, UserRole

OWNER = "module:authz"


class AdminAuthorityService:
    def __init__(
        self, database: Database, audit: AuditSink, events: EventPublisher, *, clock: Clock | None = None
    ) -> None:
        self.database = database
        self.audit = audit
        self.events = events
        self.clock = clock

    async def _lock(self, session: AsyncSession) -> AdminSingleton:
        return (
            await session.execute(select(AdminSingleton).where(AdminSingleton.id == 1).with_for_update())
        ).scalar_one()

    async def current_admin(self, session: AsyncSession) -> UUID | None:
        return await session.scalar(
            select(AdminSingleton.current_admin_user_id).where(AdminSingleton.id == 1)
        )

    async def is_admin(self, session: AsyncSession, user_id: UUID) -> bool:
        return (await self.current_admin(session)) == user_id

    async def grant_first_admin(self, session: AsyncSession, user_id: UUID) -> None:
        singleton = await self._lock(session)
        if singleton.current_admin_user_id is not None:
            raise AdminAlreadyExists("an Admin already exists; use the transfer")
        now = utc_now(self.clock)
        session.add(UserRole(user_id=user_id, role_id=ADMIN_ROLE_ID, granted_by=None, granted_at=now))
        singleton.current_admin_user_id = user_id
        singleton.version += 1
        await session.flush()
        await self._record(session, "admin.first_granted", None, user_id, "allow", "success")

    async def transfer_admin(
        self, session: AsyncSession, from_user: UUID, to_user: UUID, actor: Principal
    ) -> None:
        singleton = await self._lock(session)
        if singleton.current_admin_user_id != from_user or from_user == to_user:
            await self.record_refused_attempt(actor, from_user, to_user, "not_current_admin_or_same_user")
            raise AdminTransferRefused("the transfer would not leave exactly one Admin")
        now = utc_now(self.clock)
        await session.execute(
            update(UserRole)
            .where(
                UserRole.role_id == ADMIN_ROLE_ID,
                UserRole.user_id == from_user,
                UserRole.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await session.flush()
        session.add(
            UserRole(user_id=to_user, role_id=ADMIN_ROLE_ID, granted_by=actor.user_id, granted_at=now)
        )
        singleton.current_admin_user_id = to_user
        singleton.version += 1
        await session.flush()
        await self._record(
            session, "admin.transferred", actor, to_user, "allow", "success", from_user=from_user
        )

    async def record_refused_attempt(
        self, actor: Principal | None, from_user: UUID | None, to_user: UUID, reason: str
    ) -> None:
        """Refused attempts are recorded in their own transaction (the caller's one is rolled back)."""
        async with self.database.unit_of_work() as uow:
            await self._record(
                uow.session,
                "admin.transfer_refused",
                actor,
                to_user,
                "deny",
                "failure",
                from_user=from_user,
                reason=reason,
            )

    async def _record(
        self,
        session: AsyncSession,
        action: str,
        actor: Principal | None,
        target: UUID,
        decision: str,
        result: str,
        **context: object,
    ) -> None:
        details = {key: str(value) if value is not None else None for key, value in context.items()}
        await self.events.publish(
            session,
            "permission.admin_transfer_attempted",
            {"action": action, "result": result, **details},
            occurred_at=utc_now(self.clock),
            actor=actor,
            subject=SubjectRef("user", str(target)),
            source="authz",
        )
        await self.audit.record(
            session,
            AuditRecord(
                action=action,
                actor=actor,
                resource=ResourceRef(kind="user", id=str(target)),
                decision=decision,  # type: ignore[arg-type]
                result=result,  # type: ignore[arg-type]
                context=details,
                sensitive=True,
            ),
        )


def register_admin_authority(registry: CapabilityRegistry, service: AdminAuthorityService) -> None:
    registry.provide(CAPABILITY, service, instance_ref="authz", owner=OWNER)
