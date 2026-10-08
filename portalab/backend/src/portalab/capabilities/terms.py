"""Terms of use port (027): whether a member still has to accept the terms in force — what a module asks
before opening a service to them (an approved service's access, for instance)."""

from typing import Protocol, runtime_checkable
from uuid import UUID

from portalab.capabilities.registry import CapabilitySpec

CAPABILITY = "privacy.terms"


@runtime_checkable
class TermsGate(Protocol):
    async def must_accept(self, user_id: UUID) -> bool:
        """True while the member has not accepted the version of the terms in force."""
        ...


SPEC = CapabilitySpec(
    name=CAPABILITY,
    version="1.0",
    protocol=TermsGate,
    multi_provider=False,
    description="Whether a member accepted the terms of use in force (027)",
)
