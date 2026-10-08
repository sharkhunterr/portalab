"""Identity provider ports (027): the homelab's single sign-on (Authentik) holds the accounts and the groups
that open each service. ``identity.provisioning`` lets the portal find or create a member's account there,
put it in a service's group (or take it out) and get a link for the member to set their password — what an
administrator approving a service's access asks for."""

from typing import Protocol, runtime_checkable

from portalab.capabilities.registry import CapabilitySpec

PROVISIONING = "identity.provisioning"


@runtime_checkable
class IdentityProvisioning(Protocol):
    async def find_user(self, email: str | None, username: str | None) -> str | None:
        """The provider's id of the account with this email (else this username), or ``None``."""
        ...

    async def create_user(self, username: str, name: str, email: str | None) -> str:
        """Create an active account; returns its id."""
        ...

    async def add_to_group(self, user: str, group: str) -> None:
        """Put the account in the group named ``group`` (which grants a service)."""
        ...

    async def remove_from_group(self, user: str, group: str) -> None: ...

    async def recovery_link(self, user: str) -> str | None:
        """A one-time link for the member to set their password, when the provider can make one."""
        ...


SPECS: tuple[CapabilitySpec, ...] = (
    CapabilitySpec(
        name=PROVISIONING,
        version="1.0",
        protocol=IdentityProvisioning,
        multi_provider=True,
        description="Accounts and groups in the identity provider, for a service's access (027)",
    ),
)
