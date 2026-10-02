"""Contribution isolation (T007; R6, FR-010): rejected or failing contributions are recorded — aggregated
per ``(owner, key, reason)`` with a count — and announced once as ``navigation.contribution_rejected``;
the rest of the navigation is unaffected."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.navigation import Rejection
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.logging import redact_text
from portalab.core.time import Clock, utc_now
from portalab.modules.shell.models import ContributionError
from portalab.modules.shell.observability import metrics


class Isolator:
    def __init__(self, database: Database, events: EventPublisher, *, clock: Clock | None = None) -> None:
        self.database = database
        self.events = events
        self.clock = clock

    async def record(self, rejections: list[Rejection]) -> int:
        if not rejections:
            return 0
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            for rejection in rejections:
                existing = (
                    await uow.session.execute(
                        select(ContributionError.id).where(
                            ContributionError.owner == rejection.owner,
                            ContributionError.key == rejection.key,
                            ContributionError.reason == rejection.reason,
                        )
                    )
                ).scalar_one_or_none()
                await uow.session.execute(
                    insert(ContributionError)
                    .values(
                        owner=rejection.owner[:128],
                        key=rejection.key[:128],
                        reason=rejection.reason,
                        detail=redact_text(rejection.detail)[:512],
                        first_seen_at=now,
                        last_seen_at=now,
                        count=1,
                    )
                    .on_conflict_do_update(
                        constraint="uq_contribution_errors",
                        set_={"count": ContributionError.count + 1, "last_seen_at": now},
                    )
                )
                if existing is None:
                    await self.events.publish(
                        uow.session,
                        "navigation.contribution_rejected",
                        {
                            "contributor": rejection.owner,
                            "contribution": rejection.key,
                            "reason": rejection.reason,
                        },
                        occurred_at=now,
                        source="shell",
                    )
                metrics.increment("shell.rejected_contributions")
        return len(rejections)

    async def errors(self) -> list[dict[str, Any]]:
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(ContributionError).order_by(ContributionError.last_seen_at.desc())
                )
            ).scalars()
            return [
                {
                    "owner": r.owner,
                    "key": r.key,
                    "reason": r.reason,
                    "detail": r.detail,
                    "count": r.count,
                    "first_seen_at": r.first_seen_at.isoformat(),
                    "last_seen_at": r.last_seen_at.isoformat(),
                }
                for r in rows
            ]
