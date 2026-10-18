"""Grants (spec 030, FR-005-FR-007): the capabilities the Admin accepted for one version of a plugin.

Approving a version 2 plugin's review accepts every capability its manifest asks (the review lists them in
plain words); one capability can be revoked at any time, which takes effect at once (the next request
needing it is refused). Every change is audited.
"""

import time
from collections.abc import Mapping
from typing import Any

from sqlalchemy import select

from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import NotFound
from portalab.core.time import Clock, utc_now
from portalab.modules.plugins.manifest.schema import CAPABILITIES, Manifest
from portalab.modules.plugins.models import Grant

# what each capability means, in the Admin's words (the review; translated in locales/*/plugins.json)
DESCRIPTIONS: dict[str, str] = {
    "storage": "Keep its own data (a separate storage, within a quota).",
    "operations": "Offer its own actions to members, each with a permission it declares.",
    "permissions": "Declare permissions you can give to roles.",
    "pages": "Add pages and navigation entries, drawn by Portalab.",
    "slots": "Add content to places of Portalab's screens (drawn by Portalab).",
    "live": "Send live updates to members through Portalab.",
    "events": "Receive and send portal events.",
    "jobs": "Run background jobs in Portalab's worker.",
    "notifications": "Send notifications to members (their preferences apply).",
    "search": "Add results to the portal's search (filtered by members' rights).",
    "moderation": "Use moderation on what members post in it.",
    "privacy": "Export and erase what it keeps about a member.",
    "product_types": "Add kinds of products to the shop (the shop keeps coins and ownership).",
    "settings": "Have settings, its secrets kept by Portalab.",
    "network": "Reach the outside hosts listed here, through Portalab.",
    "portal_data": "Read portal data through the operations listed here, with the member's rights.",
    "visual_types": "Add kinds of visuals packs can bring and the shop can sell (drawn by the plugin).",
}


def parameters_of(manifest: Manifest, capability: str) -> dict[str, Any]:
    value = manifest.capabilities.get(capability)
    if capability == "network":
        return {"hosts": manifest.network_hosts}
    if capability == "portal_data":
        return {"operations": manifest.portal_operations, "job_permissions": manifest.job_permissions}
    if capability == "permissions":
        return {"names": [str(p["name"]) for p in manifest.raw.get("permissions", [])]}
    if capability == "product_types" and manifest.shelves:
        # where the shop shows them, reviewed with the kinds themselves
        shelves = [
            {"key": x["key"], "department": x["department"], "types": list(x["types"])}
            for x in manifest.shelves
        ]
        return {"names": list(value or []), "shelves": shelves}
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, list):
        return {"names": list(value)}
    return {}


def review_items(manifest: Manifest) -> list[dict[str, Any]]:
    """What the review shows: each requested capability, its words, its parameters."""
    return [
        {"capability": name, "description": DESCRIPTIONS[name], "parameters": parameters_of(manifest, name)}
        for name in manifest.requested_capabilities()
        if name in CAPABILITIES
    ]


class Grants:
    def __init__(self, database: Database, audit: AuditSink, *, clock: Clock | None = None) -> None:
        self.database = database
        self.audit = audit
        self.clock = clock
        # a short cache: a revocation made by another process (serve / worker) is seen within seconds
        self._cache: dict[tuple[str, str], tuple[float, dict[str, dict[str, Any]]]] = {}
        self.ttl = 5.0

    async def grant_all(self, actor: Principal, key: str, version: str, manifest: Manifest) -> list[str]:
        now = utc_now(self.clock)
        names = [n for n in manifest.requested_capabilities() if n in CAPABILITIES]
        async with self.database.unit_of_work() as uow:
            session = uow.session
            existing = {
                g.capability: g
                for g in (
                    await session.execute(
                        select(Grant).where(Grant.plugin_key == key, Grant.version == version)
                    )
                ).scalars()
            }
            for name in names:
                grant = existing.get(name)
                if grant is None:
                    session.add(
                        Grant(
                            plugin_key=key,
                            version=version,
                            capability=name,
                            parameters=parameters_of(manifest, name),
                            granted_by=actor.acting_for or actor.user_id,
                            granted_at=now,
                        )
                    )
                else:
                    grant.parameters = parameters_of(manifest, name)
                    grant.revoked_at = None
                    grant.granted_at = now
                    grant.granted_by = actor.acting_for or actor.user_id
            await self.audit.record(
                session,
                AuditRecord(
                    action="plugin.capabilities_granted",
                    actor=actor,
                    resource=ResourceRef("plugin", key),
                    decision="allow",
                    context={"version": version, "capabilities": names},
                    sensitive=True,
                ),
            )
        self._cache.pop((key, version), None)
        return names

    async def revoke(self, actor: Principal, key: str, version: str, capability: str) -> None:
        async with self.database.unit_of_work() as uow:
            session = uow.session
            grant = await session.scalar(
                select(Grant).where(
                    Grant.plugin_key == key, Grant.version == version, Grant.capability == capability
                )
            )
            if grant is None or grant.revoked_at is not None:
                raise NotFound("This capability is not granted.", code="plugin.grant_not_found")
            grant.revoked_at = utc_now(self.clock)
            await self.audit.record(
                session,
                AuditRecord(
                    action="plugin.capability_revoked",
                    actor=actor,
                    resource=ResourceRef("plugin", key),
                    decision="allow",
                    context={"version": version, "capability": capability},
                    sensitive=True,
                ),
            )
        self._cache.pop((key, version), None)

    async def active(self, key: str, version: str) -> dict[str, dict[str, Any]]:
        cached = self._cache.get((key, version))
        if cached is not None and time.monotonic() - cached[0] < self.ttl:
            return cached[1]
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(Grant).where(
                        Grant.plugin_key == key, Grant.version == version, Grant.revoked_at.is_(None)
                    )
                )
            ).scalars()
            granted = {g.capability: dict(g.parameters or {}) for g in rows}
        self._cache[(key, version)] = (time.monotonic(), granted)
        return granted

    async def listed(self, key: str, version: str) -> list[dict[str, Any]]:
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(Grant)
                    .where(Grant.plugin_key == key, Grant.version == version)
                    .order_by(Grant.capability)
                )
            ).scalars()
            return [
                {
                    "capability": g.capability,
                    "description": DESCRIPTIONS.get(g.capability, g.capability),
                    "parameters": dict(g.parameters or {}),
                    "granted_at": g.granted_at,
                    "revoked_at": g.revoked_at,
                }
                for g in rows
            ]

    async def carry_over(self, key: str, version: str, manifest: Manifest) -> bool:
        """An update asking nothing more than what the running version was granted keeps those grants (FR-006:
        only an update asking more is reviewed again). Returns whether every capability is now granted."""
        async with self.database.session() as session:
            rows = list(
                (
                    await session.execute(
                        select(Grant)
                        .where(Grant.plugin_key == key, Grant.version != version, Grant.revoked_at.is_(None))
                        .order_by(Grant.granted_at.desc())
                    )
                ).scalars()
            )
        if not rows:
            return False
        latest = rows[0].version
        previous = {g.capability: dict(g.parameters or {}) for g in rows if g.version == latest}
        for name in manifest.requested_capabilities():
            if name not in CAPABILITIES:
                continue
            if name not in previous or not _within(parameters_of(manifest, name), previous[name]):
                return False
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            for name in manifest.requested_capabilities():
                if name not in CAPABILITIES:
                    continue
                exists = await session.scalar(
                    select(Grant).where(
                        Grant.plugin_key == key, Grant.version == version, Grant.capability == name
                    )
                )
                if exists is None:
                    session.add(
                        Grant(
                            plugin_key=key,
                            version=version,
                            capability=name,
                            parameters=parameters_of(manifest, name),
                            granted_by=None,  # carried over from the version the Admin reviewed
                            granted_at=now,
                        )
                    )
        self._cache.pop((key, version), None)
        return True

    async def missing(self, key: str, version: str, manifest: Manifest) -> list[str]:
        granted = await self.active(key, version)
        return [n for n in manifest.requested_capabilities() if n in CAPABILITIES and n not in granted]

    def forget(self, key: str) -> None:
        for cached in [k for k in self._cache if k[0] == key]:
            self._cache.pop(cached, None)


def _within(asked: Mapping[str, Any], granted: Mapping[str, Any]) -> bool:
    """``asked`` reaches no further than ``granted`` (lists included in theirs, quotas no larger)."""
    for name, value in asked.items():
        had = granted.get(name)
        if isinstance(value, list):
            known = [repr(v) for v in had] if isinstance(had, list) else []
            if any(repr(v) not in known for v in value):
                return False
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            if not isinstance(had, (int, float)) or value > had:
                return False
        elif value != had:
            return False
    return True
