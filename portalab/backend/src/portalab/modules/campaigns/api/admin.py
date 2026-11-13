"""Campaign console API (T007, T013, T025, T027; ``campaigns.manage`` — sensitive, audited): create, publish a
new version (confirmation when the campaign is active), activate / deactivate / cancel (reason and
confirmation), archive, simulate (no writes), history, and a manual announcement through 010 (also needs
``notifications.broadcast``)."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from portalab.capabilities.confirmations import CAPABILITY as CONFIRMATIONS
from portalab.capabilities.notifications import NOTIFY, AllAuthenticated, CommunicationRequest
from portalab.core.audit_port import AuditRecord
from portalab.core.authorization import require
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.errors import Conflict, Forbidden, Unavailable
from portalab.core.time import utc_now
from portalab.modules.campaigns.api.public import Module
from portalab.modules.campaigns.definitions.service import CampaignNotFound
from portalab.modules.campaigns.models import (
    ActivationLog,
    Campaign,
    CampaignVersion,
    Occurrence,
    OpenInterval,
    Override,
)
from portalab.modules.campaigns.module import ANNOUNCEMENT
from portalab.modules.campaigns.permissions import MANAGE
from portalab.modules.campaigns.simulate.service import simulate

router = APIRouter(prefix="/api/v1", tags=["campaigns-admin"])
Manager = Annotated[Principal, require(MANAGE)]
BROADCAST = "notifications.broadcast"


class ConfirmationRequired(Conflict):
    default_code = "authz.confirmation_required"
    default_title = "Confirmation required"


class CampaignCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=2, max_length=64)
    definition: dict[str, Any]
    draft: bool = False


class CampaignUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    definition: dict[str, Any]
    confirmation: str | None = None


class CampaignOverrideIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=3, max_length=200)
    until: datetime | None = None
    confirmation: str | None = None


class CampaignSimulateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_type: str = Field(min_length=3, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)
    user_id: UUID | None = None
    at: datetime | None = None


class CampaignAnnounceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(default="", max_length=500)


class CampaignOut(BaseModel):
    id: UUID
    key: str
    state: str
    current_version: int
    timezone: str
    definition: dict[str, Any]
    created_at: datetime


async def _confirm(
    module: Any, principal: Principal, action: str, campaign_id: UUID, token: str | None
) -> None:
    providers = module.capabilities.system_providers(CONFIRMATIONS)
    if not providers:
        raise Unavailable("Confirmations are not available.", code="authz.unavailable")
    confirmations = providers[0].provider
    resource = ResourceRef("campaign", str(campaign_id))
    payload = {"action": action}
    if token is None:
        issued = await confirmations.issue(principal, MANAGE, resource, payload)
        raise ConfirmationRequired("Confirm this campaign change.", extensions={"confirmation": issued})
    if not await confirmations.consume(token, principal, MANAGE, resource, payload):
        raise Forbidden("The confirmation is invalid or expired.", code="authz.confirmation_invalid")


async def _out(module: Any, campaign_id: UUID) -> CampaignOut:
    campaign, definition = await module.definitions.get(campaign_id)
    return CampaignOut(
        id=campaign.id,
        key=campaign.key,
        state=campaign.state,
        current_version=campaign.current_version,
        timezone=campaign.timezone,
        definition=definition.model_dump(mode="json"),
        created_at=campaign.created_at,
    )


@router.get("/admin/campaigns", response_model=list[CampaignOut])
async def list_campaigns(_: Manager, module: Module) -> list[CampaignOut]:
    return [await _out(module, c.id) for c in await module.definitions.all()]


@router.post("/admin/campaigns", response_model=CampaignOut, status_code=201)
async def create(principal: Manager, body: CampaignCreateIn, module: Module) -> CampaignOut:
    campaign = await module.definitions.create(principal, body.key, body.definition, draft=body.draft)
    await module.reconciler.run()
    return await _out(module, campaign.id)


@router.get("/admin/campaigns/{campaign_id}", response_model=CampaignOut)
async def get(_: Manager, campaign_id: UUID, module: Module) -> CampaignOut:
    return await _out(module, campaign_id)


@router.put(
    "/admin/campaigns/{campaign_id}",
    response_model=CampaignOut,
    responses={409: {"description": "authz.confirmation_required (carries `confirmation`) when active"}},
)
async def publish(
    principal: Manager, campaign_id: UUID, body: CampaignUpdateIn, module: Module
) -> CampaignOut:
    campaign, _ = await module.definitions.get(campaign_id)
    if campaign.state == "active":
        await _confirm(module, principal, "publish", campaign_id, body.confirmation)
    await module.definitions.publish(principal, campaign_id, body.definition)
    await module.reconciler.run()
    return await _out(module, campaign_id)


async def _override(
    principal: Principal,
    campaign_id: UUID,
    body: CampaignOverrideIn,
    module: Any,
    kind: Literal["activate", "deactivate"],
) -> CampaignOut:
    await _confirm(module, principal, kind, campaign_id, body.confirmation)
    await module.overrides.apply(principal, campaign_id, kind, body.reason, body.until)
    return await _out(module, campaign_id)


@router.post("/admin/campaigns/{campaign_id}/activate", response_model=CampaignOut)
async def activate(
    principal: Manager, campaign_id: UUID, body: CampaignOverrideIn, module: Module
) -> CampaignOut:
    return await _override(principal, campaign_id, body, module, "activate")


@router.post("/admin/campaigns/{campaign_id}/deactivate", response_model=CampaignOut)
async def deactivate(
    principal: Manager, campaign_id: UUID, body: CampaignOverrideIn, module: Module
) -> CampaignOut:
    return await _override(principal, campaign_id, body, module, "deactivate")


@router.post("/admin/campaigns/{campaign_id}/cancel", response_model=CampaignOut)
async def cancel(
    principal: Manager, campaign_id: UUID, body: CampaignOverrideIn, module: Module
) -> CampaignOut:
    await _confirm(module, principal, "cancel", campaign_id, body.confirmation)
    await module.definitions.cancel(principal, campaign_id, body.reason)
    return await _out(module, campaign_id)


@router.post("/admin/campaigns/{campaign_id}/archive", response_model=CampaignOut)
async def archive(principal: Manager, campaign_id: UUID, module: Module) -> CampaignOut:
    await module.definitions.archive(principal, campaign_id)
    return await _out(module, campaign_id)


@router.post("/admin/campaigns/{campaign_id}/simulate")
async def simulate_campaign(
    principal: Manager, campaign_id: UUID, body: CampaignSimulateIn, module: Module
) -> list[dict[str, Any]]:
    campaign, _ = await module.definitions.get(campaign_id)
    user = body.user_id or principal.acting_for or principal.user_id
    assert user is not None
    return await simulate(
        module.simulation, campaign.key, user, body.event_type, body.payload, body.at or utc_now(module.clock)
    )


@router.get("/admin/campaigns/{campaign_id}/history")
async def history(_: Manager, campaign_id: UUID, module: Module) -> dict[str, Any]:
    async with module.database.session() as session:
        campaign = await session.get(Campaign, campaign_id)
        if campaign is None:
            raise CampaignNotFound("This campaign does not exist.")
        versions = (
            await session.execute(
                select(CampaignVersion)
                .where(CampaignVersion.campaign_id == campaign_id)
                .order_by(CampaignVersion.version)
            )
        ).scalars()
        occurrences = (
            await session.execute(
                select(Occurrence).where(Occurrence.campaign_id == campaign_id).order_by(Occurrence.index)
            )
        ).scalars()
        log = (
            await session.execute(
                select(ActivationLog)
                .where(ActivationLog.campaign_id == campaign_id)
                .order_by(ActivationLog.during)
            )
        ).scalars()
        open_row = await session.get(OpenInterval, campaign_id)
        overrides = (
            await session.execute(
                select(Override).where(Override.campaign_id == campaign_id).order_by(Override.created_at)
            )
        ).scalars()
        return {
            "versions": [
                {
                    "version": v.version,
                    "effective_from": v.effective_from.isoformat(),
                    "definition": v.definition,
                }
                for v in versions
            ],
            "occurrences": [
                {
                    "id": str(o.id),
                    "index": o.index,
                    "version": o.version,
                    "start_at": o.start_at.isoformat(),
                    "end_at": o.end_at.isoformat(),
                    "status": o.status,
                }
                for o in occurrences
            ],
            "intervals": [
                {
                    "opened_at": i.during.lower.isoformat() if i.during.lower else None,
                    "closed_at": i.during.upper.isoformat() if i.during.upper else None,
                    "version": i.version,
                    "cause": i.cause,
                    "reason": i.reason,
                }
                for i in log
            ]
            + (
                [
                    {
                        "opened_at": open_row.opened_at.isoformat(),
                        "closed_at": None,
                        "version": open_row.version,
                        "cause": open_row.cause,
                        "reason": open_row.reason,
                    }
                ]
                if open_row
                else []
            ),
            "overrides": [
                {
                    "kind": o.kind,
                    "from_at": o.from_at.isoformat(),
                    "until_at": o.until_at.isoformat() if o.until_at else None,
                    "reason": o.reason,
                    "expired_at": o.expired_at.isoformat() if o.expired_at else None,
                }
                for o in overrides
            ],
        }


@router.post("/admin/campaigns/{campaign_id}/announce")
async def announce(
    principal: Manager, campaign_id: UUID, body: CampaignAnnounceIn, module: Module
) -> dict[str, Any]:
    if not await module.authorizer.is_allowed(principal, BROADCAST):
        raise Forbidden("You cannot broadcast announcements.", code="campaign.announce_forbidden")
    campaign, definition = await module.definitions.get(campaign_id)
    providers = module.capabilities.system_providers(NOTIFY)
    if not providers:
        raise Unavailable("Notifications are not available.", code="notifications.unavailable")
    now = utc_now(module.clock)
    reference = await providers[0].provider.send(
        CommunicationRequest(
            category=ANNOUNCEMENT,
            template_key="campaigns:notify.announcement",
            audience=AllAuthenticated(),
            dedup_key=f"campaign-announcement:{campaign.id}:{now.strftime('%Y%m%d%H%M')}",
            kind="notification",
            # issue 398: the campaign's name in each member's language (the names by language)
            params={"campaign": dict(definition.names) or definition.name(), "message": body.message},
            source="module",
            source_ref=f"campaign:{campaign.key}",
            action_url=f"/campaigns/{campaign.key}",
        ),
        caller=principal,
    )
    async with module.database.unit_of_work() as uow:
        await module.audit.record(
            uow.session,
            AuditRecord(
                action="campaign.announced",
                actor=principal,
                resource=ResourceRef("campaign", str(campaign.id)),
                decision="allow",
                context={"campaign": campaign.key, "recipients": reference.recipients},
                sensitive=True,
            ),
        )
    return {"communication": str(reference.id), "recipients": reference.recipients}
