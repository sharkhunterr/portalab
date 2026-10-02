"""Discovery (T019; FR-005/006, US2).

Probes **only** the targets the operator supplies (no network scanning), records candidates, and never
configures or enables anything by itself: a candidate becomes a ``configured`` service only on an explicit
confirm; a declined candidate stays recorded and is offered again by a later discovery of the same target.
"""

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from portalab.core.authz_port import Principal
from portalab.core.errors import Conflict, NotFound, ValidationFailed
from portalab.core.logging import redact
from portalab.core.time import utc_now
from portalab.modules.connectors.models import DiscoveryCandidate
from portalab.modules.connectors.observability import log
from portalab.modules.connectors.services.common import audit, publish
from portalab.modules.connectors.services.manager import SYSTEM, ServiceManager

MAX_TARGETS = 32
MAX_TARGET_LENGTH = 512


class CandidateNotFound(NotFound):
    default_code = "discovery.not_found"


class CandidateClosed(Conflict):
    default_code = "discovery.already_confirmed"
    default_title = "This candidate was already confirmed"


class DiscoveryService:
    def __init__(self, manager: ServiceManager) -> None:
        self.manager = manager

    async def discover(
        self, actor: Principal, connector_key: str, targets: Sequence[str]
    ) -> list[dict[str, Any]]:
        connector = self.manager.connector(connector_key)
        cleaned = sorted({target.strip() for target in targets if target and target.strip()})
        if not cleaned or len(cleaned) > MAX_TARGETS or any(len(t) > MAX_TARGET_LENGTH for t in cleaned):
            raise ValidationFailed(
                f"Provide between 1 and {MAX_TARGETS} targets to probe.", code="discovery.invalid_targets"
            )
        try:
            candidates = await asyncio.wait_for(
                connector.discover(cleaned), timeout=self.manager.config.http_timeout_seconds * 3
            )
        except Exception as exc:
            log.warning(
                "discovery failed",
                extra={"fields": {"connector": connector_key, "error": type(exc).__name__}},
            )
            candidates = []
        allowed = set(cleaned)
        now = utc_now(self.manager.clock)
        found: list[dict[str, Any]] = []
        async with self.manager.database.unit_of_work() as uow:
            for candidate in candidates:
                if candidate.target not in allowed:  # a connector may not report targets it was not given
                    continue
                details = redact(dict(candidate.details))
                statement = (
                    insert(DiscoveryCandidate)
                    .values(
                        connector_key=connector_key,
                        target=candidate.target,
                        details=details,
                        status="candidate",
                        found_at=now,
                    )
                    .on_conflict_do_update(
                        constraint="uq_discovery_candidates_target",
                        set_={"details": details, "found_at": now, "status": "candidate"},
                        where=DiscoveryCandidate.status != "confirmed",
                    )
                    .returning(DiscoveryCandidate.id)
                )
                candidate_id = (await uow.session.execute(statement)).scalar_one_or_none()
                if candidate_id is None:
                    continue  # already confirmed as a service
                await publish(
                    self.manager.events,
                    uow.session,
                    "connector.discovered",
                    {"connector": connector_key, "candidate_id": str(candidate_id)},
                    service_id=None,
                    actor=actor,
                    occurred_at=now,
                )
                found.append({"id": str(candidate_id), "target": candidate.target, "details": details})
            await audit(
                self.manager.audit,
                uow.session,
                "connector.discovery_run",
                actor,
                context={"connector": connector_key, "targets": len(cleaned), "found": len(found)},
                sensitive=False,
            )
        return found

    async def list(self, connector_key: str | None = None) -> list[dict[str, Any]]:
        async with self.manager.database.session() as session:
            statement = select(DiscoveryCandidate).order_by(DiscoveryCandidate.found_at.desc())
            if connector_key:
                statement = statement.where(DiscoveryCandidate.connector_key == connector_key)
            return [_view(row) for row in (await session.execute(statement)).scalars()]

    async def confirm(
        self,
        actor: Principal,
        candidate_id: UUID,
        *,
        name: str,
        config: Mapping[str, Any] | None = None,
        secrets: Mapping[str, str | None] | None = None,
    ) -> UUID:
        async with self.manager.database.unit_of_work() as uow:
            row = await uow.session.get(DiscoveryCandidate, candidate_id, with_for_update=True)
            if row is None:
                raise CandidateNotFound("No such discovery candidate.")
            if row.status == "confirmed":
                raise CandidateClosed("This candidate is already a configured service.")
            merged = {**dict(row.details.get("config", {})), **(config or {})}
            service_id = await self.manager.configure(
                actor,
                connector_key=row.connector_key,
                name=name,
                config=merged,
                secrets=secrets,
                session=uow.session,
            )
            row.status, row.service_id = "confirmed", service_id
        return service_id

    async def decline(self, actor: Principal, candidate_id: UUID) -> dict[str, Any]:
        async with self.manager.database.unit_of_work() as uow:
            row = await uow.session.get(DiscoveryCandidate, candidate_id, with_for_update=True)
            if row is None:
                raise CandidateNotFound("No such discovery candidate.")
            if row.status == "confirmed":
                raise CandidateClosed("This candidate is already a configured service.")
            row.status = "declined"
            await audit(
                self.manager.audit,
                uow.session,
                "connector.candidate_declined",
                actor or SYSTEM,
                context={"connector": row.connector_key},
                sensitive=False,
            )
            return _view(row)


def _view(row: DiscoveryCandidate) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "connector": row.connector_key,
        "target": row.target,
        "details": dict(row.details),
        "status": row.status,
        "found_at": row.found_at.isoformat(),
        "service_id": str(row.service_id) if row.service_id else None,
    }
