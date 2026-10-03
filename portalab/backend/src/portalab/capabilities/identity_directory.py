"""``identity.directory`` capability contract (spec 002 contracts) — who a user is, for other modules.

``is_active_account`` is the single eligibility check for "active account" capabilities (voting, rewards):
only the ``active`` state qualifies. Tombstoned users return an anonymized summary (no display name).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, runtime_checkable
from uuid import UUID

from portalab.capabilities.registry import CapabilitySpec

CAPABILITY = "identity.directory"
CONTACT = "identity.contact"
MEMBERS = "identity.members"
VERIFICATION_CHANNEL = "identity.verification_channel"

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


@runtime_checkable
class ContactReader(Protocol):
    """Contact data for system delivery (Notifications 010): never exposed to other users."""

    async def email_of(self, user_id: UUID) -> str | None: ...

    async def active_user_ids(self) -> list[UUID]: ...


@runtime_checkable
class VerificationChannel(Protocol):
    """How a verification/invitation token reaches a person (implemented by Notifications' email channel);
    without a provider, the Admin hands the token over (spec 002 baseline)."""

    async def deliver(self, user_id: UUID, token: str, expires_at: datetime) -> None: ...


CONTACT_SPEC = CapabilitySpec(
    name=CONTACT,
    version="1.0",
    protocol=ContactReader,
    multi_provider=False,
    description="E-mail address and active accounts for system delivery (owned by identity).",
)
VERIFICATION_SPEC = CapabilitySpec(
    name=VERIFICATION_CHANNEL,
    version="1.0",
    protocol=VerificationChannel,
    multi_provider=False,
    description="Delivers verification and invitation tokens (e-mail by Notifications 010).",
)


@dataclass(frozen=True, slots=True)
class MemberEntry:
    id: UUID
    display_name: str
    joined_at: datetime


@dataclass(frozen=True, slots=True)
class MemberPage:
    items: tuple[MemberEntry, ...]
    next_offset: int | None = None


@runtime_checkable
class MemberListing(Protocol):
    """Active accounts with a display name, ordered by name (Community directory 012). Visibility is the
    caller's job (021): this only lists who *could* be shown."""

    async def active_members(
        self, *, query: str | None = None, offset: int = 0, limit: int = 30, newest: bool = False
    ) -> MemberPage: ...


MEMBERS_SPEC = CapabilitySpec(
    name=MEMBERS,
    version="1.0",
    protocol=MemberListing,
    multi_provider=False,
    description="Active members by display name (owned by identity).",
)
