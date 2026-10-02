"""Configuration import/export (T020; R9, FR-016).

Export: a versioned JSON document of global/module/plugin values — sensitive values and user preferences
are never included. Import: validate every entry → conflict report (values that differ from the current
ones are listed, never silently overwritten) → apply only when the caller confirms the listed conflicts.
"""

from dataclasses import dataclass, field
from typing import Any

from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal
from portalab.core.errors import ValidationFailed
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock, utc_now
from portalab.modules.administration.config.registry import UnknownSetting
from portalab.modules.administration.config.resolution import MISSING
from portalab.modules.administration.config.service import Change, ConfigService
from portalab.modules.administration.models import Setting

FORMAT = "portalab.configuration"
FORMAT_VERSION = 1


@dataclass
class ImportReport:
    applied: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)


class ImportExportService:
    def __init__(
        self, config: ConfigService, audit: AuditSink, events: EventPublisher, *, clock: Clock | None = None
    ):
        self.config = config
        self.audit = audit
        self.events = events
        self.clock = clock

    async def export(self, actor: Principal) -> dict[str, Any]:
        from sqlalchemy import select

        entries = []
        async with self.config.database.session() as session:
            rows = list(
                (
                    await session.execute(
                        select(Setting).where(Setting.scope != "user").order_by(Setting.key)
                    )
                ).scalars()
            )
        for row in rows:
            try:
                declaration = self.config.registry.declaration(row.key)
            except UnknownSetting:
                continue  # a value left by an uninstalled plugin: kept in the store, not exported
            if declaration.sensitive:
                continue
            value = self.config.decode(declaration, row)
            if value is MISSING:
                continue
            entries.append({"key": row.key, "scope": row.scope, "scope_ref": row.scope_ref, "value": value})
        document = {
            "format": FORMAT,
            "format_version": FORMAT_VERSION,
            "exported_at": utc_now(self.clock).isoformat(),
            "settings": entries,
        }
        await self._record(actor, "admin.export_performed", {"entries": len(entries)})
        return document

    async def import_(
        self, actor: Principal, document: dict[str, Any], *, accept_conflicts: list[str]
    ) -> ImportReport:
        if document.get("format") != FORMAT or document.get("format_version") != FORMAT_VERSION:
            raise ValidationFailed("Unsupported configuration document.", code="admin.import_format")
        report = ImportReport()
        changes: list[Change] = []
        for entry in document.get("settings", []):
            change = Change(
                str(entry.get("key")),
                entry.get("value"),
                str(entry.get("scope", "global")),
                str(entry.get("scope_ref", "")),
            )
            if change.scope == "user":
                report.errors.append({"key": change.key, "detail": "user preferences are not imported"})
                continue
            preview = await self.config.validate([change])
            if not preview.ok:
                report.errors.extend({"key": e["key"], "detail": e["detail"]} for e in preview.errors)
                continue
            declaration = self.config.registry.declaration(change.key)
            if declaration.sensitive:
                report.errors.append({"key": change.key, "detail": "sensitive values are never imported"})
                continue
            current = await self.config.stored_value(change.key, change.scope, change.scope_ref)
            normalized = declaration.validate(change.value)
            if current is not MISSING and current == normalized:
                report.unchanged.append(change.key)
                continue
            ident = f"{change.scope}:{change.scope_ref}:{change.key}"
            if current is not MISSING and ident not in accept_conflicts:
                report.conflicts.append(
                    {"id": ident, "key": change.key, "current": current, "incoming": normalized}
                )
                continue
            changes.append(change)
            report.applied.append(change.key)
        if changes and not report.errors and not report.conflicts:
            await self.config.apply(changes, actor, reason="configuration import")
        else:
            report.applied = []
        await self._record(
            actor,
            "admin.import_performed",
            {
                "applied": len(report.applied),
                "conflicts": len(report.conflicts),
                "errors": len(report.errors),
            },
        )
        return report

    async def _record(self, actor: Principal, action: str, context: dict[str, Any]) -> None:
        async with self.config.database.unit_of_work() as uow:
            await self.events.publish(
                uow.session,
                action,
                context,
                occurred_at=utc_now(self.clock),
                actor=actor,
                source="administration",
            )
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action=action,
                    actor=actor,
                    decision="allow",
                    result="success",
                    context=context,
                    sensitive=True,
                ),
            )
