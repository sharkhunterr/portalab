"""032: a household profile has no media-service account of its own — it watches with its master's (the shared
account the family uses at home). Whoever reaches a service through the portal goes with the account of the
member holding the link: the profile's master, else the member themself."""

from uuid import UUID

from portalab.capabilities.household import CAPABILITY as HOUSEHOLD
from portalab.capabilities.registry import CapabilityRegistry


async def link_holder(capabilities: CapabilityRegistry, user: UUID) -> UUID:
    """The member whose media-service links ``user`` uses."""
    try:
        providers = capabilities.system_providers(HOUSEHOLD)
        owner = await providers[0].provider.owner_of(user) if providers else None
    except Exception:
        owner = None
    return owner or user
