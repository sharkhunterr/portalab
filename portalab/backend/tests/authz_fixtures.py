"""003 T002 — shared authorization fixtures: real engine on PostgreSQL, users, roles, grants, principals
(including the ``ai | automation | plugin`` channels that act for a user)."""

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import text

from portalab.capabilities.catalog import new_registry
from portalab.core.authz_port import Principal
from portalab.core.blobstore import FileSystemBlobStore
from portalab.core.db import Database
from portalab.core.event_port import OutboxEventPublisher
from portalab.core.time import Clock
from portalab.modules.authz.grants.service import GrantSpec
from portalab.modules.authz.module import AuthzModule
from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.settings import IdentityConfig
from tests.identity_fakes import FAST_ARGON2

INSERT_USER = text(
    "INSERT INTO identity.users (id, login, display_name, display_name_key, state, transition_seq, "
    "state_changed_at, created_at, updated_at) "
    "VALUES (:id, :login, :login, :login, 'active', 1, now(), now(), now())"
)


@dataclass
class AuthzPlatform:
    authz: AuthzModule
    identity: IdentityContext

    @property
    def database(self) -> Database:
        return self.authz.database


def make_platform(database: Database, blob_root: Path, clock: Clock | None = None) -> AuthzPlatform:
    capabilities = new_registry()
    events = OutboxEventPublisher(clock)
    authz = AuthzModule(database, events, capabilities, clock=clock)
    authz.register_capabilities()
    identity = IdentityContext(
        database=database,
        events=events,
        audit=authz.audit,
        capabilities=capabilities,
        blobs=FileSystemBlobStore(blob_root),
        authorizer=authz.engine,
        config=IdentityConfig(argon2_params=FAST_ARGON2),
        **({"clock": clock} if clock else {}),  # type: ignore[arg-type]
    )
    return AuthzPlatform(authz, identity)


async def insert_user(database: Database, login: str | None = None) -> UUID:
    user_id = uuid4()
    async with database.engine.begin() as conn:
        await conn.execute(INSERT_USER, {"id": user_id, "login": login or f"u{user_id.hex[:10]}"})
    return user_id


async def make_admin(platform: AuthzPlatform, user_id: UUID) -> None:
    async with platform.database.unit_of_work() as uow:
        await platform.authz.admin_authority.grant_first_admin(uow.session, user_id)


async def grant_role(platform: AuthzPlatform, role_key: str, spec: GrantSpec) -> None:
    async with platform.database.session() as session:
        role_id = await session.scalar(text("SELECT id FROM authz.roles WHERE key = :k"), {"k": role_key})
    await platform.authz.grants.add_grant(None, "role", role_id, spec)


def user(user_id: UUID) -> Principal:
    return Principal(user_id=user_id)


def ai(user_id: UUID) -> Principal:
    return Principal(channel="ai", acting_for=user_id)


def automation(user_id: UUID) -> Principal:
    return Principal(channel="automation", acting_for=user_id)


def plugin(user_id: UUID) -> Principal:
    return Principal(channel="plugin", acting_for=user_id)


SYSTEM_ACTOR = Principal(channel="system")
