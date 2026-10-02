"""``authz.user_grants`` capability (spec 003 F15, consumed by 015 Marketplace activation and 023 plugins).

Grants an *entitlement* permission (declared ``user_grantable``, e.g. ``plugin:<key>.use`` or an allow-listed
``access`` product) to one user. Reserved permissions are never grantable this way.
"""

from typing import Protocol, runtime_checkable
from uuid import UUID

from portalab.capabilities.registry import CapabilitySpec

CAPABILITY = "authz.user_grants"


@runtime_checkable
class UserGrants(Protocol):
    async def grant(
        self,
        user_id: UUID,
        permission_key: str,
        *,
        scope_kind: str = "global",
        scope_ref: str = "",
        source: str,
    ) -> None: ...

    async def revoke(
        self, user_id: UUID, permission_key: str, *, scope_kind: str = "global", scope_ref: str = ""
    ) -> bool: ...


SPEC = CapabilitySpec(
    name=CAPABILITY,
    version="1.0",
    protocol=UserGrants,
    multi_provider=False,
    description="Per-user entitlement grants (allow-listed permissions only).",
)
