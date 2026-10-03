"""Resolution (T013; R3, R4, R6): funds are never moved silently — only per the frozen rules.

* a project **rejected or abandoned** releases every still-reserved tranche (a new ledger transaction per
  reservation; ``project.funding_released``);
* reaching a **milestone** on the forward path consumes the tranches due at that state (``consume_at``;
  ``released`` by default; ``project.funding_consumed``);
* everything runs inside the transition's transaction and is idempotent (settled tranches are skipped), so
  a re-run (job or retry) changes nothing;
* ``reconcile`` compares every tranche with its 013 reservation and reports the drift."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.economy import ECONOMY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.errors import Unavailable
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.marketplace.models import Project, ProjectFunding
from portalab.modules.marketplace.observability import metrics
from portalab.modules.marketplace.projects.state import reached

OPEN_STATUSES = ("reserved", "partially_consumed")
LEDGER_STATUS = {
    "reserved": "active",
    "released": "released",
    "consumed": "consumed",
    "destroyed": "destroyed",
}


class Resolution:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        capabilities: CapabilityRegistry,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.capabilities = capabilities
        self.clock = clock

    def economy(self) -> Any:
        providers = self.capabilities.system_providers(ECONOMY)
        if not providers:
            raise Unavailable("The economy is not available.", code="economy.unavailable")
        return providers[0].provider

    async def _open_fundings(self, session: AsyncSession, project: Project) -> list[ProjectFunding]:
        return list(
            (
                await session.execute(
                    select(ProjectFunding)
                    .where(ProjectFunding.project_id == project.id, ProjectFunding.status.in_(OPEN_STATUSES))
                    .order_by(ProjectFunding.created_at, ProjectFunding.id)
                    .with_for_update()
                )
            ).scalars()
        )

    async def settle(self, session: AsyncSession, project: Project, actor: Any) -> int:
        """Apply the rules for the project's (new) state; returns the number of tranches settled."""
        if project.state in ("rejected", "abandoned"):
            return await self._each(session, project, actor, lambda tranche: True, "release")
        return await self._each(
            session, project, actor, lambda tranche: reached(project.state, tranche["consume_at"]), "consume"
        )

    async def _each(
        self,
        session: AsyncSession,
        project: Project,
        actor: Any,
        due: Callable[[dict[str, Any]], bool],
        action: str,
    ) -> int:
        fundings = await self._open_fundings(session, project)
        if not fundings:
            return 0
        economy = self.economy()
        settled = 0
        now = utc_now(self.clock)
        for funding in fundings:
            moved = 0
            tranches = [dict(t) for t in funding.tranches]
            for tranche in tranches:
                if tranche["status"] != "reserved" or not due(tranche):
                    continue
                reservation = UUID(tranche["reservation"])
                if action == "release":
                    await economy.release(reservation, reason=f"project {project.state}", session=session)
                    tranche["status"] = "released"
                else:
                    await economy.consume(reservation, session=session)
                    tranche["status"] = "consumed"
                moved += int(tranche["amount"])
                settled += 1
            if not moved:
                continue
            funding.tranches = tranches
            statuses = {t["status"] for t in tranches}
            if statuses == {"released"}:
                funding.status, funding.resolved_at = "released", now
            elif statuses == {"consumed"}:
                funding.status, funding.resolved_at = "consumed", now
            elif "reserved" in statuses and "consumed" in statuses:
                funding.status = "partially_consumed"
            else:
                funding.status, funding.resolved_at = "consumed", now  # consumed then released remainder
            event = "project.funding_released" if action == "release" else "project.funding_consumed"
            await self.events.publish(
                session,
                event,
                {"project": str(project.id), "funding": str(funding.id), "amount": moved},
                occurred_at=now,
                actor=actor,
                subject=SubjectRef("user", str(funding.user_id)),
                dedup_key=f"{event}:{funding.id}:{project.state}",
            )
            metrics.increment(
                f"marketplace.funding.{'released' if action == 'release' else 'consumed'}", moved
            )
        return settled

    async def reconcile(self) -> dict[str, int]:
        """Tranches whose 013 reservation disagrees with the recorded status (should always be zero)."""
        async with self.database.session() as session:
            fundings = list((await session.execute(select(ProjectFunding))).scalars())
        tranches = [(f, t) for f in fundings for t in f.tranches]
        found = {
            str(r.id): r.status
            for r in await self.economy().reservations([UUID(t["reservation"]) for _, t in tranches])
        }
        drift = sum(
            1
            for _, t in tranches
            if found.get(t["reservation"]) != LEDGER_STATUS.get(t["status"], t["status"])
        )
        return {"tranches": len(tranches), "drift": drift}
