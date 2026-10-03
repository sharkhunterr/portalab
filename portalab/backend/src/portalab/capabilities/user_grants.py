"""``authz.user_grants`` capability (spec 003 F15, consumed by 015 Marketplace activation and 023 plugins).

Grants an *entitlement* permission (declared ``user_grantable``, e.g. ``plugin:<key>.use`` or an allow-listed
``access`` product) to one user. Reserved permissions are never grantable this way.
"""

from typing import Protocol, runtime_checkable
from uuid import UUID

from portalab.capabilities.registry import CapabilitySpec

CAPABILITY = "authz.user_grants"
ROLES_CAPABILITY = "authz.user_roles"


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


@runtime_checkable
class UserRoles(Protocol):
    """Role keys held by a user, including the implicit ``user`` role (read-only; spec 009 ``role_in``)."""

    async def roles_of(self, user_id: UUID) -> frozenset[str]: ...


ROLES_SPEC = CapabilitySpec(
    name=ROLES_CAPABILITY,
    version="1.0",
    protocol=UserRoles,
    multi_provider=False,
    description="Role keys of a user (for closed-set display conditions; never an authorization check).",
)
