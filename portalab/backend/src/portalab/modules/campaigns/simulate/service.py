"""Simulation (T027; R13): runs a sample occurrence through the real resolver, audience and conditions and
reports which modifiers would apply — **no writes** (attribute failures are not even counted)."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from portalab.capabilities.events import Envelope
from portalab.modules.campaigns.modifiers.provider import CampaignModifiers


async def simulate(
    modifiers: CampaignModifiers,
    campaign_key: str,
    user: UUID,
    event_type: str,
    payload: dict[str, Any],
    at: datetime,
) -> list[dict[str, Any]]:
    event = Envelope(
        event_id=uuid4(),
        seq=0,
        type=event_type,
        type_version=1,
        occurred_at=at,
        received_at=at,
        source_system="simulation",
        source_event_id=None,
        actor_user_id=user,
        actor_kind="user",
        subject_type=None,
        subject_id=None,
        payload=payload,
        provenance={},
        correlation_id=None,
    )
    return [
        {
            "modifier": item.modifier,
            "value": item.value,
            "factor": item.factor,
            "version": item.version,
            "verdict": item.verdict,
            "source_ref": f"campaign:{item.campaign}:{item.version}:{item.modifier}",
        }
        for item in await modifiers.explain(user, event, at)
        if item.campaign == campaign_key
    ]
