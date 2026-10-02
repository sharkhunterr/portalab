"""Admin visibility overrides (T013; FR-005..008, R3).

An override is a ``visibility_policies`` row; the user's preference is never read for writing nor changed.
Removing (or letting ``ends_at`` pass) restores the preference automatically. One active row per
(subject, datum class): a second ``apply`` is refused (no stacking, OQ-100). Both actions are audited as
sensitive admin actions and emit ``privacy.override_applied|removed``.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.visibility import DatumClassRegistry, default_datum_classes
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound, ValidationFailed
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.privacy.models import VisibilityPolicy
from portalab.modules.privacy.observability import metrics

FORCED_LEVELS = {"force_private": ("private",), "force_visible": ("public", "community", "leaderboard")}


@dataclass(frozen=True, slots=True)
class PolicyRequest:
    datum_class: str
    mode: str
    reason: str
    subject_user_id: UUID | None = None
    level: str | None = None
    ends_at: datetime | None = None


class PolicyService:
    def __init__(
        self,
        database: Database,
        audit: AuditSink,
        events: EventPublisher,
        *,
        datum_classes: DatumClassRegistry = default_datum_classes,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.audit = audit
        self.events = events
        self.datum_classes = datum_classes
        self.clock = clock

    def _validate(self, request: PolicyRequest, now: datetime) -> str | None:
        if self.datum_classes.get(request.datum_class) is None:
            raise ValidationFailed("Unknown datum class.", code="privacy.unknown_datum_class")
        if request.mode == "user_choice":
            if request.level is not None:
                raise ValidationFailed("'user_choice' takes no level.", code="privacy.invalid_policy")
            return None
        allowed = FORCED_LEVELS.get(request.mode)
        if allowed is None:
            raise ValidationFailed("Unknown mode.", code="privacy.invalid_policy")
        level = request.level or ("private" if request.mode == "force_private" else None)
        if level not in allowed:
            raise ValidationFailed("This level does not match the mode.", code="privacy.invalid_policy")
        if request.ends_at is not None and request.ends_at <= now:
            raise ValidationFailed("The end date must be in the future.", code="privacy.invalid_policy")
        return level

    async def _expire(self, session: AsyncSession, now: datetime) -> None:
        """Close rows whose ``ends_at`` passed so that a new policy may be applied (history kept)."""
        await session.execute(
            update(VisibilityPolicy)
            .where(VisibilityPolicy.removed_at.is_(None), VisibilityPolicy.ends_at <= now)
            .values(removed_at=VisibilityPolicy.ends_at)
        )

    async def _record(
        self, session: AsyncSession, event: str, actor: Principal, policy: VisibilityPolicy
    ) -> None:
        details: dict[str, Any] = {
            "policy_id": str(policy.id),
            "datum_class": policy.datum_class,
            "mode": policy.mode,
            "level": policy.level,
            "subject": str(policy.subject_user_id) if policy.subject_user_id else "all",
        }
        subject = SubjectRef("user", str(policy.subject_user_id)) if policy.subject_user_id else None
        await self.events.publish(
            session,
            event,
            details,
            occurred_at=utc_now(self.clock),
            actor=actor,
            subject=subject,
            source="privacy",
            dedup_key=f"{event}:{policy.id}",
        )
        await self.audit.record(
            session,
            AuditRecord(
                action=event,
                actor=actor,
                resource=ResourceRef("visibility_policy", str(policy.id), owner_id=policy.subject_user_id),
                decision="allow",
                result="success",
                context=details,
                sensitive=True,
            ),
        )

    async def apply(self, actor: Principal, request: PolicyRequest) -> VisibilityPolicy:
        now = utc_now(self.clock)
        level = self._validate(request, now)
        async with self.database.unit_of_work() as uow:
            await self._expire(uow.session, now)
            policy = VisibilityPolicy(
                subject_user_id=request.subject_user_id,
                datum_class=request.datum_class,
                mode=request.mode,
                level=level,
                reason=request.reason.strip()[:256],
                set_by=actor.user_id,
                set_at=now,
                ends_at=request.ends_at,
            )
            uow.session.add(policy)
            try:
                async with uow.session.begin_nested():
                    await uow.session.flush()
            except IntegrityError as exc:
                if "uq_visibility_policies_active" in str(exc.orig):
                    raise Conflict(
                        "An override is already active for this data; remove it first.",
                        code="privacy.policy_exists",
                    ) from exc
                raise NotFound("Unknown user.", code="user.not_found") from exc
            await self._record(uow.session, "privacy.override_applied", actor, policy)
        metrics.increment("privacy.overrides.applied")
        return policy

    async def remove(self, actor: Principal, policy_id: UUID) -> VisibilityPolicy:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            policy = await uow.session.get(VisibilityPolicy, policy_id, with_for_update=True)
            if policy is None or policy.removed_at is not None:
                raise NotFound("No active override with this id.", code="privacy.policy_not_found")
            policy.removed_at = now
            policy.removed_by = actor.user_id
            await self._record(uow.session, "privacy.override_removed", actor, policy)
        metrics.increment("privacy.overrides.removed")
        return policy

    async def list_active(self, subject: UUID | None = None) -> list[VisibilityPolicy]:
        now = utc_now(self.clock)
        statement = select(VisibilityPolicy).where(
            VisibilityPolicy.removed_at.is_(None),
            or_(VisibilityPolicy.ends_at.is_(None), VisibilityPolicy.ends_at > now),
        )
        if subject is not None:
            statement = statement.where(
                or_(VisibilityPolicy.subject_user_id == subject, VisibilityPolicy.subject_user_id.is_(None))
            )
        async with self.database.session() as session:
            policies = list((await session.execute(statement.order_by(VisibilityPolicy.set_at))).scalars())
        if subject is None:
            metrics.gauge("privacy.overrides.active", len(policies))
        return policies
