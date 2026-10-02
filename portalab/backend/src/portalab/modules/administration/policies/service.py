"""Configuration policies (T010; R2): ``default`` (informational admin default), ``lock`` (user values
ignored) and ``bound`` (user values outside ``bounds`` ignored, new ones refused). One active policy per key;
rows are history (``removed_at``); user values are never deleted, so removing a policy restores them."""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound, ValidationFailed
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock, utc_now
from portalab.modules.administration.config.registry import SettingRegistry, is_user_overridable
from portalab.modules.administration.models import Policy
from portalab.modules.administration.observability import metrics


class PolicyService:
    def __init__(
        self,
        database: Database,
        registry: SettingRegistry,
        audit: AuditSink,
        events: EventPublisher,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.registry = registry
        self.audit = audit
        self.events = events
        self.clock = clock

    async def _record(self, session: Any, action: str, actor: Principal, policy: Policy) -> None:
        details = {
            "policy_id": str(policy.id),
            "setting": policy.key,
            "mode": policy.mode,
            "bounds": policy.bounds,
        }
        await self.events.publish(
            session,
            "admin.policy_changed",
            {**details, "action": action},
            occurred_at=utc_now(self.clock),
            actor=actor,
            source="administration",
            dedup_key=f"admin.policy:{policy.id}:{action}",
        )
        await self.audit.record(
            session,
            AuditRecord(
                action=f"admin.policy_{action}",
                actor=actor,
                resource=ResourceRef("setting_policy", str(policy.id)),
                decision="allow",
                result="success",
                context=details,
                sensitive=True,
            ),
        )

    async def apply(self, actor: Principal, key: str, mode: str, bounds: dict[str, Any] | None) -> Policy:
        declaration = self.registry.declaration(key)
        if not is_user_overridable(declaration) and mode != "default":
            raise ValidationFailed(
                "Only user-overridable settings take lock/bound policies.", code="admin.invalid_policy"
            )
        if mode == "bound" and not bounds:
            raise ValidationFailed("A bound policy needs bounds.", code="admin.invalid_policy")
        if bounds and not set(bounds) <= {"min", "max", "allowed"}:
            raise ValidationFailed("Bounds accept min, max and allowed.", code="admin.invalid_policy")
        async with self.database.unit_of_work() as uow:
            policy = Policy(
                key=key, mode=mode, bounds=bounds, set_by=actor.user_id, set_at=utc_now(self.clock)
            )
            uow.session.add(policy)
            try:
                async with uow.session.begin_nested():
                    await uow.session.flush()
            except IntegrityError as exc:
                raise Conflict(
                    "A policy is already active for this setting.", code="admin.policy_exists"
                ) from exc
            await self._record(uow.session, "applied", actor, policy)
        metrics.increment("admin.policies.applied")
        return policy

    async def remove(self, actor: Principal, policy_id: UUID) -> None:
        async with self.database.unit_of_work() as uow:
            policy = await uow.session.get(Policy, policy_id, with_for_update=True)
            if policy is None or policy.removed_at is not None:
                raise NotFound("No active policy with this id.", code="admin.policy_not_found")
            policy.removed_at = utc_now(self.clock)
            await self._record(uow.session, "removed", actor, policy)
        metrics.increment("admin.policies.removed")

    async def active(self) -> list[Policy]:
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(Policy).where(Policy.removed_at.is_(None)).order_by(Policy.key)
                    )
                ).scalars()
            )
