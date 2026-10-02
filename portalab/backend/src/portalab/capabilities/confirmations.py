"""``authz.confirmations`` capability: issue/consume single-use confirmation tokens (spec 003 R10).

Lets other modules (privacy purge, AI, automations) require an explicit confirmation without importing
the authorization module.
"""

from typing import Any, Protocol, runtime_checkable

from portalab.capabilities.registry import CapabilitySpec
from portalab.core.authz_port import Principal, ResourceRef

CAPABILITY = "authz.confirmations"


@runtime_checkable
class Confirmations(Protocol):
    async def issue(
        self, principal: Principal, permission: str, resource: ResourceRef | None, payload: Any
    ) -> str: ...

    async def consume(
        self, token: str, principal: Principal, permission: str, resource: ResourceRef | None, payload: Any
    ) -> bool: ...


SPEC = CapabilitySpec(
    name=CAPABILITY,
    version="1.0",
    protocol=Confirmations,
    multi_provider=False,
    description="Single-use confirmation tokens bound to principal, permission, resource and payload.",
)
