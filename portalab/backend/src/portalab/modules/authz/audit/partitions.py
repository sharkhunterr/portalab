"""Audit partition maintenance (T019): create next months ahead of time, drop partitions older than the
retention window (``privacy.retention.auditMonths``). Job ``audit_partition_maintenance``."""

from datetime import datetime

from portalab.core.db import Database
from portalab.core.partitions import drop_month_partitions_before, ensure_month_partitions, month_start
from portalab.modules.authz.observability import log

SCHEMA, TABLE = "audit", "audit_entries"


def retention_cutoff(now: datetime, months: int) -> datetime:
    start = month_start(now)
    year, month = start.year, start.month - months
    while month <= 0:
        month += 12
        year -= 1
    return now.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)


async def maintain(
    database: Database, now: datetime, *, retention_months: int | None
) -> dict[str, list[str]]:
    async with database.unit_of_work() as uow:
        created = await ensure_month_partitions(uow.session, SCHEMA, TABLE, now)
        dropped: list[str] = []
        if retention_months is not None:
            dropped = await drop_month_partitions_before(
                uow.session, SCHEMA, TABLE, retention_cutoff(now, retention_months)
            )
    log.info(
        "audit partitions maintained", extra={"fields": {"created": len(created), "dropped": len(dropped)}}
    )
    return {"created": created, "dropped": dropped}
