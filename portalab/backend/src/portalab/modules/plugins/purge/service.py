"""Purge (T019; R8, FR-005/007/023): disabling or archiving a plugin never deletes data. Deleting it is a
separate, permissioned (``plugins.purge``), confirmed (API) and audited action, refused while the plugin is
enabled: optionally export the plugin's tables first (JSON under ``plugins/exports``), then drop the plugin
schema and role. Core data is never touched; the purge is recorded (append-only)."""

import json

from portalab.core.audit_port import AuditRecord
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.event_port import SubjectRef
from portalab.core.time import utc_now
from portalab.modules.plugins.lifecycle.service import InvalidState, Lifecycle
from portalab.modules.plugins.models import Purge


class Purges:
    def __init__(self, lifecycle: Lifecycle) -> None:
        self.lifecycle = lifecycle

    async def purge(self, actor: Principal, key: str, *, export: bool) -> Purge:
        plugin = await self.lifecycle.get(key)
        if plugin.state in ("enabled", "update_pending"):
            raise InvalidState("Disable the plugin before deleting its data.", code="plugin.enabled")
        now = utc_now(self.lifecycle.clock)
        export_ref = None
        if export:
            data = await self.lifecycle.storage.export(key)
            folder = self.lifecycle.store.root / "exports"
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / f"{key}-{now.strftime('%Y%m%dT%H%M%SZ')}.json"
            target.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            export_ref = str(target)
        existed = await self.lifecycle.storage.exists(key)
        await self.lifecycle.storage.drop(key)
        row = Purge(
            plugin_key=key,
            requested_by=actor.acting_for or actor.user_id,
            exported=export,
            export_ref=export_ref,
            executed_at=now,
            schema_dropped=existed,
        )
        async with self.lifecycle.database.unit_of_work() as uow:
            uow.session.add(row)
            await self.lifecycle.events.publish(
                uow.session,
                "plugin.purged",
                {"plugin": key, "version": plugin.current_version},
                occurred_at=now,
                actor=actor,
                subject=SubjectRef("plugin", key),
                dedup_key=f"plugin.purged:{key}:{now.isoformat()}",
            )
            await self.lifecycle.audit.record(
                uow.session,
                AuditRecord(
                    action="plugin.purged",
                    actor=actor,
                    resource=ResourceRef("plugin", key),
                    decision="allow",
                    context={"exported": export, "schema_dropped": existed},
                    sensitive=True,
                ),
            )
        return row
