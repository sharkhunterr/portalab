"""Automations (T007, T011, T027): drafts and **append-only versions** — every save is a new version; the
published version is what runs. Publishing validates against today's registries, checks a system identity
never exceeds its publisher, and attests standing approvals for the sensitive (non-destructive) actions it
contains (the API requires a confirmation then). State machine: draft → active ⇄ paused, active → suspended
(automatic) → active (explicit re-enable), any → archived. Every change is audited."""

import re
from collections.abc import Callable, Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from portalab.capabilities.automation_actions import ActionRegistry
from portalab.capabilities.automations import ConditionRegistry
from portalab.capabilities.events import EventTypeRegistry
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.permissions import PermissionRegistry
from portalab.core.time import Clock, utc_now
from portalab.modules.automations.definitions.schema import Definition
from portalab.modules.automations.definitions.validate import effective_sensitivity, validate
from portalab.modules.automations.identity.guard import IdentityGuard
from portalab.modules.automations.models import Automation, AutomationVersion, ScheduleState

KEY = r"^[a-z0-9][a-z0-9_-]{1,63}$"
TRANSITIONS = {
    "pause": ({"active"}, "paused", "automation.paused"),
    "resume": ({"paused"}, "active", "automation.resumed"),
    "reenable": ({"suspended"}, "active", "automation.resumed"),
    "archive": ({"draft", "active", "paused", "suspended"}, "archived", "automation.archived"),
}


class AutomationNotFound(NotFound):
    default_code = "automation.not_found"
    default_title = "Automation not found"


class Definitions:
    def __init__(
        self,
        database: Database,
        audit: AuditSink,
        events: EventPublisher,
        guard: IdentityGuard,
        *,
        types: EventTypeRegistry,
        actions: ActionRegistry,
        conditions: ConditionRegistry,
        permissions: PermissionRegistry,
        config: Any,
        on_change: Callable[[], None] = lambda: None,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.audit = audit
        self.events = events
        self.guard = guard
        self.types = types
        self.actions = actions
        self.conditions = conditions
        self.permissions = permissions
        self.config = config
        self.on_change = on_change
        self.clock = clock

    def validate(self, raw: Mapping[str, Any]) -> Definition:
        return validate(
            raw,
            types=self.types,
            actions=self.actions,
            conditions=self.conditions,
            permissions=self.permissions,
            max_steps=self.config().max_steps,
        )

    def sensitive_actions(self, definition: Definition) -> dict[str, str]:
        out = {}
        for step in definition.steps:
            action = self.actions.get(step.action)
            if action is not None:
                level = effective_sensitivity(action, self.permissions)
                if level != "normal":
                    out[action.key] = level
        return out

    async def _audit(
        self, session: Any, actor: Principal, action: str, automation: Automation, **context: Any
    ) -> None:
        await self.audit.record(
            session,
            AuditRecord(
                action=action,
                actor=actor,
                resource=ResourceRef("automation", str(automation.id)),
                decision="allow",
                context={"automation": automation.key, **context},
                sensitive=True,
            ),
        )

    async def _event(
        self, session: Any, name: str, automation: Automation, actor: Principal, **extra: Any
    ) -> None:
        await self.events.publish(
            session,
            name,
            {"automation": automation.key, **extra},
            occurred_at=utc_now(self.clock),
            actor=actor,
            subject=SubjectRef("automation", str(automation.id)),
            dedup_key=f"{name}:{automation.id}:{automation.current_version}:{utc_now(self.clock).isoformat()}",
        )

    async def create(self, actor: Principal, key: str, raw: Mapping[str, Any]) -> Automation:
        if not re.fullmatch(KEY, key):
            raise ValidationFailed("Invalid automation key.", code="automation.invalid_definition")
        definition = self.validate(raw)
        owner = actor.acting_for or actor.user_id
        if owner is None:
            raise Forbidden("Automations are authored by a person.", code="automation.action_forbidden")
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            if await uow.session.scalar(select(Automation.id).where(Automation.key == key)) is not None:
                raise Conflict("An automation with this key exists.", code="automation.duplicate")
            automation = Automation(
                key=key,
                name=definition.name,
                state="draft",
                current_version=1,
                owner_user_id=owner,
                identity_kind=definition.identity.kind,
                system_scopes=list(definition.identity.scopes) or None,
                created_at=now,
                updated_at=now,
            )
            uow.session.add(automation)
            await uow.session.flush()
            uow.session.add(
                AutomationVersion(
                    automation_id=automation.id,
                    version=1,
                    definition=definition.model_dump(mode="json", by_alias=True),
                    published_by=owner,
                    published_at=now,
                    standing_approvals=[],
                )
            )
            await self._audit(uow.session, actor, "automation.created", automation, version=1)
            await self._event(uow.session, "automation.created", automation, actor, version=1)
            return automation

    async def update(self, actor: Principal, automation_id: UUID, raw: Mapping[str, Any]) -> Automation:
        definition = self.validate(raw)
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            automation = await uow.session.get(Automation, automation_id, with_for_update=True)
            if automation is None:
                raise AutomationNotFound("This automation does not exist.")
            if automation.state == "archived":
                raise Conflict("Archived automations cannot change.", code="automation.archived")
            automation.current_version += 1
            automation.name, automation.updated_at = definition.name, now
            uow.session.add(
                AutomationVersion(
                    automation_id=automation.id,
                    version=automation.current_version,
                    definition=definition.model_dump(mode="json", by_alias=True),
                    published_by=actor.acting_for or actor.user_id,
                    published_at=now,
                    standing_approvals=[],
                )
            )
            await self._audit(
                uow.session, actor, "automation.saved", automation, version=automation.current_version
            )
            return automation

    async def publish(self, actor: Principal, automation_id: UUID) -> Automation:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            automation = await uow.session.get(Automation, automation_id, with_for_update=True)
            if automation is None:
                raise AutomationNotFound("This automation does not exist.")
            if automation.state == "archived":
                raise Conflict("Archived automations cannot be published.", code="automation.archived")
            version = await uow.session.get(AutomationVersion, (automation.id, automation.current_version))
            assert version is not None
            definition = self.validate(version.definition)  # still valid against today's registries
            missing = await self.guard.may_publish(actor, list(definition.identity.scopes))
            if missing:
                raise Forbidden(
                    "A system identity cannot exceed your own rights.",
                    code="automation.action_forbidden",
                    extensions={"scopes": missing},
                )
            standing = sorted(
                k for k, level in self.sensitive_actions(definition).items() if level == "sensitive"
            )
            if standing and version.standing_approvals != standing:  # attested on a new append-only version
                automation.current_version += 1
                uow.session.add(
                    AutomationVersion(
                        automation_id=automation.id,
                        version=automation.current_version,
                        definition=version.definition,
                        published_by=actor.acting_for or actor.user_id,
                        published_at=now,
                        standing_approvals=standing,
                    )
                )
            automation.published_version = automation.current_version
            automation.identity_kind = definition.identity.kind
            automation.system_scopes = list(definition.identity.scopes) or None
            automation.state = (
                "active" if automation.state in ("draft", "active", "suspended") else automation.state
            )
            automation.needs_review, automation.updated_at = False, now
            state = await uow.session.get(ScheduleState, automation.id)
            if state is not None:
                state.next_fire_at = None  # recomputed from the new trigger
            await self._audit(
                uow.session,
                actor,
                "automation.published",
                automation,
                version=automation.current_version,
                standing=standing,
            )
            await self._event(
                uow.session, "automation.published", automation, actor, version=automation.current_version
            )
        self.on_change()
        return automation

    async def transition(self, actor: Principal, automation_id: UUID, name: str) -> Automation:
        allowed, target, event = TRANSITIONS[name]
        async with self.database.unit_of_work() as uow:
            automation = await uow.session.get(Automation, automation_id, with_for_update=True)
            if automation is None:
                raise AutomationNotFound("This automation does not exist.")
            if automation.state not in allowed:
                raise Conflict(
                    f"Cannot {name} an automation that is {automation.state}.",
                    code="automation.invalid_state",
                )
            if name == "reenable":
                automation.consecutive_failures, automation.suspend_reason = 0, None
            automation.state, automation.updated_at = target, utc_now(self.clock)
            await self._audit(uow.session, actor, f"automation.{name}", automation)
            await self._event(uow.session, event, automation, actor)
        self.on_change()
        return automation

    async def get(self, automation_id: UUID) -> tuple[Automation, list[AutomationVersion]]:
        async with self.database.session() as session:
            automation = await session.get(Automation, automation_id)
            if automation is None:
                raise AutomationNotFound("This automation does not exist.")
            versions = list(
                (
                    await session.execute(
                        select(AutomationVersion)
                        .where(AutomationVersion.automation_id == automation_id)
                        .order_by(AutomationVersion.version)
                    )
                ).scalars()
            )
        return automation, versions

    async def all(self) -> list[Automation]:
        async with self.database.session() as session:
            return list(
                (await session.execute(select(Automation).order_by(Automation.created_at.desc()))).scalars()
            )

    async def count_active(self) -> int:
        async with self.database.session() as session:
            return int(
                await session.scalar(
                    select(func.count()).select_from(Automation).where(Automation.state == "active")
                )
                or 0
            )
