"""Authorization port (risk R-A, CD-002/CD-003).

The kernel only defines the contract. The real engine (roles, grants, scopes, Admin singularity) is planned by
spec 003 and plugs in here. Until then :class:`DenyAllAuthorizer` refuses everything: the portal is
deny-by-default from its very first route.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol
from uuid import UUID

Channel = Literal["user", "system", "ai", "automation", "plugin"]


@dataclass(frozen=True, slots=True)
class Principal:
    """Who is acting. AI/automations/plugins act *for* a user and never get more rights (CD-003)."""

    user_id: UUID | None = None
    channel: Channel = "user"
    acting_for: UUID | None = None
    session_id: UUID | None = None  # set by identity's session resolver (spec 002, ``identity.principal``)

    @property
    def is_authenticated(self) -> bool:
        return self.user_id is not None or self.channel == "system"


ANONYMOUS = Principal()


@dataclass(frozen=True, slots=True)
class ResourceRef:
    """What is acted upon (structural scope evaluated by the authorization engine)."""

    kind: str
    id: str | None = None
    owner_id: UUID | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)


class Authorizer(Protocol):
    async def is_allowed(
        self, principal: Principal, permission: str, resource: ResourceRef | None = None
    ) -> bool: ...


class DenyAllAuthorizer:
    """Default until the authorization engine (spec 003) is installed."""

    async def is_allowed(
        self, principal: Principal, permission: str, resource: ResourceRef | None = None
    ) -> bool:
        return False
