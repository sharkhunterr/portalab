"""Shared pieces of the identity services: actors, problem codes, audit (fail-closed) and event helpers."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.audit_port import AuditRecord
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.errors import BadRequest, Conflict, Forbidden, NotFound, Unauthorized, Unavailable
from portalab.core.event_port import PublishResult, SubjectRef
from portalab.core.logging import get_logger
from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.domain.state_machine import ActorKind

log = get_logger("portalab.identity")

SYSTEM_PRINCIPAL = Principal(channel="system")


@dataclass(frozen=True, slots=True)
class Actor:
    kind: ActorKind
    principal: Principal

    @property
    def user_id(self) -> UUID | None:
        return self.principal.user_id


SYSTEM = Actor("system", SYSTEM_PRINCIPAL)


def self_actor(principal: Principal) -> Actor:
    return Actor("self", principal)


def admin_actor(principal: Principal) -> Actor:
    return Actor("admin", principal)


# --- problem codes (contracts/identity-contracts.md) -------------------------------------------------
class InvalidCredentials(Unauthorized):
    """Single answer for every unauthenticated failure (unknown login, wrong password, unusable account)."""

    default_code = "auth.invalid_credentials"
    default_title = "Invalid credentials"

    def __init__(self) -> None:
        super().__init__("The login or password is incorrect.")


class AccountUnavailable(Forbidden):
    """Only returned after *valid* credentials (research R4): the state may then be disclosed."""

    default_code = "auth.account_unavailable"
    default_title = "Account unavailable"


class Throttled(BadRequest):
    status = 429
    default_code = "auth.throttled"
    default_title = "Too many attempts"


class DisplayNameTaken(Conflict):
    default_code = "user.display_name_taken"
    default_title = "Display name already in use"

    def __init__(self) -> None:
        super().__init__("This display name is already in use. Choose another one.")


class SoleAdminProtected(Conflict):
    default_code = "admin.sole_admin_protected"
    default_title = "The Admin account is protected"

    def __init__(self, detail: str = "Transfer the Admin role to another account first.") -> None:
        super().__init__(detail)


class UserNotFound(NotFound):
    default_code = "user.not_found"


class AuditUnavailable(Unavailable):
    default_code = "audit.unavailable"
    default_title = "Audit unavailable"


def user_ref(user_id: UUID) -> ResourceRef:
    return ResourceRef(kind="user", id=str(user_id), owner_id=user_id)


async def audit(
    ctx: IdentityContext,
    session: AsyncSession | None,
    action: str,
    actor: Principal | None,
    *,
    resource: ResourceRef | None = None,
    result: str = "success",
    decision: str = "n/a",
    context: Mapping[str, Any] | None = None,
    sensitive: bool = False,
) -> None:
    """Write an audit record; a failure refuses a *sensitive* action and is only logged otherwise."""
    entry = AuditRecord(
        action=action,
        actor=actor,
        resource=resource,
        decision=decision,  # type: ignore[arg-type]
        result=result,  # type: ignore[arg-type]
        context=dict(context or {}),
        sensitive=sensitive,
    )
    try:
        await ctx.audit.record(session, entry)
    except Exception as exc:
        log.error("audit write failed", extra={"fields": {"action": action, "sensitive": sensitive}})
        if sensitive:
            raise AuditUnavailable("The action was refused because it could not be audited.") from exc


async def publish(
    ctx: IdentityContext,
    session: AsyncSession,
    event_type: str,
    user_id: UUID,
    *,
    actor: Principal | None,
    occurred_at: datetime,
    metadata: Mapping[str, Any] | None = None,
    dedup_key: str | None = None,
) -> PublishResult:
    return await ctx.events.publish(
        session,
        event_type,
        metadata,
        occurred_at=occurred_at,
        actor=actor,
        subject=SubjectRef("user", str(user_id)),
        source="identity",
        dedup_key=dedup_key,
    )
