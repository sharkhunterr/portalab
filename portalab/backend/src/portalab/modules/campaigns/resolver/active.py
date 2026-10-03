"""Active resolver (T020; R2, R8): which campaigns were active at an instant — an ``activation_log`` interval
containing it, or the open interval started before it — and the **version in force** at that instant. Late
and duplicate deliveries therefore resolve identically, even after the campaign ended."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, literal, select

from portalab.core.db import Database
from portalab.modules.campaigns.definitions.schema import CampaignDefinition
from portalab.modules.campaigns.models import ActivationLog, Campaign, CampaignVersion, OpenInterval


@dataclass(frozen=True, slots=True)
class ActiveCampaign:
    id: UUID
    key: str
    version: int
    definition: CampaignDefinition
    started_at: datetime
    ends_at: datetime | None


class ActiveResolver:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def at(self, instant: datetime) -> list[ActiveCampaign]:
        async with self.database.session() as session:
            logged = (
                await session.execute(
                    select(
                        ActivationLog.campaign_id,
                        func.lower(ActivationLog.during),
                        func.upper(ActivationLog.during),
                    ).where(ActivationLog.during.op("@>")(literal(instant)))
                )
            ).all()
            opened = (
                await session.execute(
                    select(OpenInterval.campaign_id, OpenInterval.opened_at).where(
                        OpenInterval.opened_at <= instant
                    )
                )
            ).all()
            windows: dict[UUID, tuple[datetime, datetime | None]] = {
                cid: (start, end) for cid, start, end in logged
            }
            for cid, start in opened:
                windows.setdefault(cid, (start, None))
            if not windows:
                return []
            campaigns = {
                c.id: c
                for c in (await session.execute(select(Campaign).where(Campaign.id.in_(windows)))).scalars()
            }
            out: list[ActiveCampaign] = []
            for cid, (start, end) in windows.items():
                version = (
                    await session.execute(
                        select(CampaignVersion)
                        .where(CampaignVersion.campaign_id == cid, CampaignVersion.effective_from <= instant)
                        .order_by(CampaignVersion.version.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if version is None or cid not in campaigns:
                    continue
                out.append(
                    ActiveCampaign(
                        cid,
                        campaigns[cid].key,
                        version.version,
                        CampaignDefinition.model_validate(version.definition),
                        start,
                        end,
                    )
                )
        return sorted(out, key=lambda c: c.key)
