"""Public campaign API (T024): what is active now for me (audience-filtered) and my effective theme overlay;
a campaign's public view (name, windows, modifier summary) for ``campaigns.read``."""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import Unavailable
from portalab.core.time import utc_now
from portalab.modules.campaigns.definitions.schema import CampaignDefinition
from portalab.modules.campaigns.definitions.service import CampaignNotFound
from portalab.modules.campaigns.models import Campaign, CampaignVersion, Occurrence
from portalab.modules.campaigns.module import CampaignsModule
from portalab.modules.campaigns.permissions import READ

router = APIRouter(prefix="/api/v1", tags=["campaigns"])
SELF = "users.self.manage"


def campaigns_module(request: Request) -> CampaignsModule:
    module = getattr(request.app.state, "campaigns_module", None)
    if not isinstance(module, CampaignsModule):
        raise Unavailable("Campaigns are not available.", code="campaigns.unavailable")
    return module


Module = Annotated[CampaignsModule, Depends(campaigns_module)]
Me = Annotated[Principal, require(SELF)]
Reader = Annotated[Principal, require(READ)]


class CampaignSummaryOut(BaseModel):
    key: str
    name: str
    ends_at: datetime | None


class CampaignPresentationOut(BaseModel):
    campaigns: list[CampaignSummaryOut]
    theme: dict[str, str] | None


def _user(principal: Principal) -> UUID:
    user = principal.acting_for or principal.user_id
    assert user is not None
    return user


@router.get("/campaigns/active", response_model=list[CampaignSummaryOut])
async def active(principal: Me, module: Module) -> list[CampaignSummaryOut]:
    return [
        CampaignSummaryOut(key=c.key, name=c.name, ends_at=c.ends_at)
        for c in await module.presentation.active_for_user(_user(principal))
    ]


@router.get("/campaigns/active/presentation", response_model=CampaignPresentationOut)
async def presentation(principal: Me, module: Module) -> CampaignPresentationOut:
    return CampaignPresentationOut.model_validate(await module.presentation.presentation(_user(principal)))


@router.get("/campaigns/{key}")
async def campaign(_: Reader, key: str, module: Module) -> dict[str, Any]:
    now = utc_now(module.clock)
    async with module.database.session() as session:
        row = (await session.execute(select(Campaign).where(Campaign.key == key))).scalar_one_or_none()
        if row is None or row.state in ("draft", "archived"):
            raise CampaignNotFound("This campaign does not exist.")
        version = await session.get(CampaignVersion, (row.id, row.current_version))
        windows = (
            await session.execute(
                select(Occurrence)
                .where(
                    Occurrence.campaign_id == row.id,
                    Occurrence.end_at > now,
                    Occurrence.status.in_(("planned", "active")),
                )
                .order_by(Occurrence.start_at)
                .limit(5)
            )
        ).scalars()
    assert version is not None
    definition = CampaignDefinition.model_validate(version.definition)
    return {
        "key": row.key,
        "name": definition.name(),
        "description": definition.description,
        "state": row.state,
        "timezone": row.timezone,
        "windows": [{"start_at": w.start_at.isoformat(), "end_at": w.end_at.isoformat()} for w in windows],
        "modifiers": [{"value": m.value, "factor": m.factor} for m in definition.modifiers],
    }
