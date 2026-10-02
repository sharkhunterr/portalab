"""``authz.admin_authority`` capability contract (spec 003 contracts; consumed by identity, spec 002).

The single-Admin invariant lives in the authorization module (CD-001, research R9 of 002): exactly one Admin,
never zero and never two, no temporary delegation. Identity only *orchestrates* bootstrap and transfer
through this contract, inside its own transaction (``session``) so account changes and the Admin change
commit together.
"""

from typing import Protocol, runtime_checkable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.registry import CapabilitySpec
from portalab.core.authz_port import Principal

CAPABILITY = "authz.admin_authority"


class AdminAuthorityError(RuntimeError):
    code = "admin.sole_admin_protected"


class AdminAlreadyExists(AdminAuthorityError):
    """A first Admin was requested while one exists (a second Admin is never created)."""


class AdminTransferRefused(AdminAuthorityError):
    """The transfer would not leave exactly one Admin (wrong holder, same user, concurrent transfer)."""


@runtime_checkable
class AdminAuthority(Protocol):
    async def current_admin(self, session: AsyncSession) -> UUID | None: ...

    async def is_admin(self, session: AsyncSession, user_id: UUID) -> bool: ...

    async def grant_first_admin(self, session: AsyncSession, user_id: UUID) -> None: ...

    async def transfer_admin(
        self, session: AsyncSession, from_user: UUID, to_user: UUID, actor: Principal
    ) -> None: ...


SPEC = CapabilitySpec(
    name=CAPABILITY,
    version="1.0",
    protocol=AdminAuthority,
    multi_provider=False,
    description="Single-Admin authority: first grant and atomic transfer (owned by authz).",
)
