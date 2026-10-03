"""Project notifications (T013): funders hear about status changes and refunds of the projects they fund,
through the 010 engine (``marketplace.project``), coalesced per project. Never blocks a transition."""

from uuid import UUID

from portalab.capabilities.notifications import NOTIFY, CommunicationRequest, Users
from portalab.capabilities.registry import CapabilityRegistry
from portalab.modules.marketplace.observability import log

CATEGORIES = {
    "marketplace.project": "marketplace:category.project",
    "marketplace.purchase": "marketplace:category.purchase",
    "marketplace.refund": "marketplace:category.refund",
    "marketplace.revocation": "marketplace:category.revocation",
}


async def notify_funders(
    capabilities: CapabilityRegistry, project_id: UUID, title: str, state: str, seq: int, funders: list[UUID]
) -> None:
    if not funders:
        return
    try:
        providers = capabilities.system_providers(NOTIFY)
        if not providers:
            return
        await providers[0].provider.send(
            CommunicationRequest(
                category="marketplace.project",
                template_key=f"marketplace:notify.project.{state}",
                audience=Users(tuple(dict.fromkeys(funders))),
                dedup_key=f"project:{project_id}:{seq}",
                params={"project": title[:120], "state": state},
                subject_ref=f"project:{project_id}",
                action_url=f"/projects/{project_id}",
            )
        )
    except Exception:
        log.warning("project notification not sent")


async def notify_owner(
    capabilities: CapabilityRegistry, user: UUID, kind: str, product: str, dedup: str
) -> None:
    """``marketplace.purchase`` / ``marketplace.refund`` to the owner (never blocks the operation)."""
    try:
        providers = capabilities.system_providers(NOTIFY)
        if not providers:
            return
        await providers[0].provider.send(
            CommunicationRequest(
                category=f"marketplace.{kind}",
                template_key=f"marketplace:notify.{kind}",
                audience=Users((user,)),
                dedup_key=dedup,
                params={"product": product[:120]},
                subject_ref=f"product:{product}",
                action_url="/marketplace/owned",
            )
        )
    except Exception:
        log.warning("marketplace notification not sent")
