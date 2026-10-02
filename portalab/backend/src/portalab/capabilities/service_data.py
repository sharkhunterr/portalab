"""``connectors.service_data`` capability (spec 021 FR-020..022; providers arrive with spec 005).

A provider owns the historized representations imported from external service instances and can purge
exactly one instance's data. Purging is never triggered by a disconnect: it is a separately authorized,
audited action (``services.purge``, CD-014).
"""

from typing import Protocol, runtime_checkable

from portalab.capabilities.registry import CapabilitySpec

CAPABILITY = "connectors.service_data"


@runtime_checkable
class ServiceDataOwner(Protocol):
    async def has_service(self, service_id: str) -> bool: ...

    async def purge_service_data(self, service_id: str) -> int: ...


SPEC = CapabilitySpec(
    name=CAPABILITY,
    version="1.0",
    protocol=ServiceDataOwner,
    multi_provider=True,
    description="Purges the historized data imported from one service instance.",
)
