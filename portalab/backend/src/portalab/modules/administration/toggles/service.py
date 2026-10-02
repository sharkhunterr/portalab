"""Enable/disable toggles (T018; R11, FR-014/015): modules, plugins, connectors, services, automations.

The toggle row is the state of record; disabling never deletes data and re-enabling restores the previous
behaviour. Before enabling, every ``admin.toggle_hook`` (spec 023 ``ModuleRegistry`` compatibility and
dependency checks) may veto. Plugins also withdraw/restore their permissions (``authz.plugin_permissions``).
"""

from sqlalchemy import select

from portalab.capabilities.administration import PLUGIN_PERMISSIONS_CAPABILITY, TOGGLE_HOOK_CAPABILITY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, ValidationFailed
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock, utc_now
from portalab.modules.administration.models import TOGGLE_KINDS, ExtensionToggle
from portalab.modules.administration.observability import metrics

PERMISSION_BY_KIND = {
    "module": "modules.manage",
    "plugin": "plugins.manage",
    "connector": "connectors.manage",
    "service": "connectors.manage",
    "automation": "automation.manage",
}


class EnableRefused(Conflict):
    default_code = "admin.enable_refused"
    default_title = "This extension cannot be enabled"


class ToggleService:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        audit: AuditSink,
        events: EventPublisher,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.audit = audit
        self.events = events
        self.clock = clock

    async def is_enabled(self, kind: str, ref: str, *, default: bool = True) -> bool:
        async with self.database.session() as session:
            row = (
                await session.execute(
                    select(ExtensionToggle.enabled).where(
                        ExtensionToggle.kind == kind, ExtensionToggle.ref == ref
                    )
                )
            ).scalar_one_or_none()
        return default if row is None else bool(row)

    async def set(
        self, actor: Principal, kind: str, ref: str, enabled: bool, reason: str = ""
    ) -> ExtensionToggle:
        if kind not in TOGGLE_KINDS:
            raise ValidationFailed("Unknown extension kind.", code="admin.unknown_toggle_kind")
        if enabled:
            problems: list[str] = []
            for registration in self.capabilities.system_providers(TOGGLE_HOOK_CAPABILITY):
                problems.extend(await registration.provider.check_enable(kind, ref))
            if problems:
                raise EnableRefused("; ".join(problems), extensions={"problems": problems})
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            row = (
                await uow.session.execute(
                    select(ExtensionToggle)
                    .where(ExtensionToggle.kind == kind, ExtensionToggle.ref == ref)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if row is None:
                row = ExtensionToggle(
                    kind=kind,
                    ref=ref,
                    enabled=enabled,
                    changed_by=actor.user_id,
                    changed_at=now,
                    reason=reason[:256],
                )
                uow.session.add(row)
            else:
                row.enabled, row.changed_by, row.changed_at, row.reason = (
                    enabled,
                    actor.user_id,
                    now,
                    reason[:256],
                )
            await uow.session.flush()
            await self.events.publish(
                uow.session,
                f"admin.{kind}_toggled",
                {"kind": kind, "ref": ref, "enabled": enabled},
                occurred_at=now,
                actor=actor,
                source="administration",
            )
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action=f"admin.{kind}_toggled",
                    actor=actor,
                    resource=ResourceRef(kind, ref),
                    decision="allow",
                    result="success",
                    context={"enabled": enabled, "reason": reason[:256]},
                    sensitive=True,
                ),
            )
        if kind == "plugin":
            for registration in self.capabilities.system_providers(PLUGIN_PERMISSIONS_CAPABILITY):
                await registration.provider.set_enabled(ref, enabled)
        metrics.increment(f"admin.toggles.{kind}")
        return row

    async def all(self) -> list[ExtensionToggle]:
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(ExtensionToggle).order_by(ExtensionToggle.kind, ExtensionToggle.ref)
                    )
                ).scalars()
            )
