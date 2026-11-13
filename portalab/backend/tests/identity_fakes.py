"""002 T006 — in-memory doubles of the spec 003 ports used by identity tests.

``RoleAuthorizer`` stands in for the authorization engine, ``RecordingAuditSink`` for the audit store and
``FakeAdminAuthority`` for ``authz.admin_authority``. They are replaced by the real 003 implementations in
003's own tests; identity tests keep them to stay independent of the engine's grant model.
"""

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.admin_authority import (
    CAPABILITY as ADMIN_AUTHORITY,
)
from portalab.capabilities.admin_authority import (
    AdminAlreadyExists,
    AdminTransferRefused,
)
from portalab.capabilities.catalog import new_registry
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.audit_port import AuditError, AuditRecord
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.blobstore import FileSystemBlobStore
from portalab.core.db import Database
from portalab.core.event_port import OutboxEventPublisher
from portalab.core.secrets import SecretBox
from portalab.core.time import Clock
from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.settings import Argon2Params, IdentityConfig

FAST_ARGON2 = Argon2Params(time_cost=1, memory_cost_kib=8192, parallelism=1)
"""Cheap parameters for tests only (production defaults are the OWASP baseline)."""

USER_PERMISSIONS = frozenset({"users.self.manage", "users.read"})
ADMIN_PERMISSIONS = frozenset(
    {"users.self.manage", "users.read", "users.manage", "users.roles.manage", "users.admin.transfer"}
)


class FakeAdminAuthority:
    def __init__(self) -> None:
        self.admin: UUID | None = None
        self.transfers: list[tuple[UUID, UUID]] = []
        self._lock = asyncio.Lock()

    async def current_admin(self, session: AsyncSession) -> UUID | None:
        return self.admin

    async def is_admin(self, session: AsyncSession, user_id: UUID) -> bool:
        return self.admin == user_id

    async def grant_first_admin(self, session: AsyncSession, user_id: UUID) -> None:
        async with self._lock:
            if self.admin is not None:
                raise AdminAlreadyExists("an Admin already exists")
            self.admin = user_id

    async def transfer_admin(
        self, session: AsyncSession, from_user: UUID, to_user: UUID, actor: Principal
    ) -> None:
        async with self._lock:
            await asyncio.sleep(0)  # let a concurrent transfer interleave
            if self.admin != from_user or from_user == to_user:
                raise AdminTransferRefused("transfer would not leave exactly one Admin")
            self.admin = to_user
            self.transfers.append((from_user, to_user))


@dataclass
class RoleAuthorizer:
    """Every authenticated user holds USER_PERMISSIONS; the current Admin holds ADMIN_PERMISSIONS."""

    authority: FakeAdminAuthority
    extra: dict[UUID, set[str]] = field(default_factory=dict)
    denied: set[str] = field(default_factory=set)

    async def is_allowed(
        self, principal: Principal, permission: str, resource: ResourceRef | None = None
    ) -> bool:
        if principal.user_id is None or permission in self.denied:
            return False
        granted = set(USER_PERMISSIONS) | self.extra.get(principal.user_id, set())
        if self.authority.admin == principal.user_id:
            granted |= ADMIN_PERMISSIONS
        return permission in granted


class RecordingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []
        self.fail = False

    async def record(self, session: AsyncSession | None, entry: AuditRecord) -> None:
        if self.fail:
            raise AuditError("audit store unavailable")
        self.records.append(entry)

    def actions(self) -> list[str]:
        return [record.action for record in self.records]


def make_registry(authority: FakeAdminAuthority | None) -> CapabilityRegistry:
    registry = new_registry()
    if authority is not None:
        registry.provide(ADMIN_AUTHORITY, authority, instance_ref="authz", owner="module:authz")
    return registry


@dataclass
class IdentityHarness:
    context: IdentityContext
    authority: FakeAdminAuthority
    audit: RecordingAuditSink
    authorizer: RoleAuthorizer


def make_context(
    database: Database,
    blob_root: Path,
    *,
    clock: Clock | None = None,
    config: IdentityConfig | None = None,
    extra_providers: Iterable[tuple[str, object, str]] = (),
) -> IdentityHarness:
    authority = FakeAdminAuthority()
    audit = RecordingAuditSink()
    authorizer = RoleAuthorizer(authority)
    registry = make_registry(authority)
    for capability, provider, ref in extra_providers:
        registry.provide(capability, provider, instance_ref=ref, owner="test")
    kwargs: dict[str, object] = {}
    if clock is not None:
        kwargs["clock"] = clock
    context = IdentityContext(
        database=database,
        events=OutboxEventPublisher(clock),
        audit=audit,
        capabilities=registry,
        blobs=FileSystemBlobStore(blob_root),
        authorizer=authorizer,
        config=config or IdentityConfig(argon2_params=FAST_ARGON2),
        **kwargs,  # type: ignore[arg-type]
        secret_box=SecretBox(b"test-only-identity-key-0123456789abcd"),
    )
    return IdentityHarness(context, authority, audit, authorizer)
