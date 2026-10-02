"""``identity.directory`` capability contract (spec 002 contracts) — who a user is, for other modules.

``is_active_account`` is the single eligibility check for "active account" capabilities (voting, rewards):
only the ``active`` state qualifies. Tombstoned users return an anonymized summary (no display name).
"""

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable
from uuid import UUID

from portalab.capabilities.registry import CapabilitySpec

CAPABILITY = "identity.directory"

AccountState = Literal[
    "pending_verification", "active", "inactive", "suspended", "pending_deletion", "deleted"
]


@dataclass(frozen=True, slots=True)
class UserSummary:
    id: UUID
    display_name: str | None  # None once the account is deleted (anonymized subject)
    state: AccountState
    is_active: bool
    anonymized: bool


@runtime_checkable
class IdentityDirectory(Protocol):
    async def get_user_summary(self, user_id: UUID) -> UserSummary | None: ...

    async def is_active_account(self, user_id: UUID) -> bool: ...

    async def exists(self, user_id: UUID) -> bool: ...


SPEC = CapabilitySpec(
    name=CAPABILITY,
    version="1.0",
    protocol=IdentityDirectory,
    multi_provider=False,
    description="User summaries and active-account eligibility (owned by identity).",
)
