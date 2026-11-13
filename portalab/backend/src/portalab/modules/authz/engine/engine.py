"""The authorization engine (T014; R1, R2, R4, R6, R8, R9).

``authorize(principal, permission, resource)`` → :class:`Decision`, deny by default:

1. the subject is the acting user — ``principal.user_id`` for the ``user`` channel, ``acting_for`` for
   ``ai | automation | plugin`` (never a superset of the user's rights; AI also needs ``ai.use``);
   ``system`` and unknown channels are denied;
2. unknown or disabled permissions never grant (a disabled plugin withdraws at the next evaluation);
3. an explicit deny in scope wins over everything, including the Admin;
4. the Admin holds every *enabled* permission; other users need an ``allow`` grant in scope; reserved
   permissions are Admin-only even if a row somehow exists;
5. sensitive permissions audit both allow and deny (fail closed: no audit ⇒ refused).

Evaluation reads the current database state; the only cache is the per-request memo.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authorization import request_memo, request_once
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Unavailable
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.authz.catalog.sync import CatalogSync
from portalab.modules.authz.engine.scopes import scope_matches
from portalab.modules.authz.grants.store import EffectiveGrants, load_effective_grants
from portalab.modules.authz.models import Permission
from portalab.modules.authz.observability import log, metrics

DELEGATED_CHANNELS = frozenset({"ai", "automation", "plugin"})


@dataclass(frozen=True, slots=True)
class Decision:
    allowed: bool
    reason: str
    scope_matched: str | None = None
    requires_confirmation: bool = False
    sensitive: bool = False


@dataclass(frozen=True, slots=True)
class PermissionInfo:
    key: str
    enabled: bool
    sensitive: bool
    reserved: bool
    requires_confirmation: bool


class AuditFailed(Unavailable):
    default_code = "audit.unavailable"
    default_title = "Audit unavailable"


class AuthorizationEngine:
    def __init__(
        self,
        database: Database,
        catalog: CatalogSync,
        audit: AuditSink,
        events: EventPublisher,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.catalog = catalog
        self.audit = audit
        self.events = events
        self.clock = clock

    # --- Authorizer port -----------------------------------------------------------------------------
    async def is_allowed(
        self, principal: Principal, permission: str, resource: ResourceRef | None = None
    ) -> bool:
        return (await self.authorize(principal, permission, resource)).allowed

    # --- evaluation ----------------------------------------------------------------------------------
    async def authorize(
        self,
        principal: Principal,
        permission: str,
        resource: ResourceRef | None = None,
        *,
        context: dict[str, Any] | None = None,
    ) -> Decision:
        try:
            decision = await self._evaluate(principal, permission, resource)
        except SQLAlchemyError as exc:
            log.error("authorization unavailable", extra={"fields": {"permission": permission}})
            raise Unavailable("Authorization is temporarily unavailable.", code="authz.unavailable") from exc
        metrics.decision(permission, decision.allowed)
        if decision.sensitive:
            await self._audit(principal, permission, resource, decision, context or {})
        return decision

    async def _evaluate(
        self, principal: Principal, permission: str, resource: ResourceRef | None
    ) -> Decision:
        subject, refusal = self._subject(principal)
        if subject is None:
            return Decision(False, refusal)
        info = await self._permission(permission)
        if info is None:
            return Decision(False, "unknown_permission")
        if not info.enabled:
            return Decision(False, "permission_disabled", sensitive=info.sensitive)
        grants = await self._grants(subject)
        decision = self._decide(info, grants, subject, resource)
        if decision.allowed and principal.channel == "ai" and permission != "ai.use":
            ai = await self._permission("ai.use")
            if ai is None or not self._decide(ai, grants, subject, None).allowed:
                return Decision(False, "ai_not_permitted", sensitive=info.sensitive)
        return decision

    @staticmethod
    def _subject(principal: Principal) -> tuple[UUID | None, str]:
        if principal.channel == "user":
            return principal.user_id, "anonymous"
        if principal.channel in DELEGATED_CHANNELS:
            return principal.acting_for, "no_acting_user"
        return None, "channel_not_authorized"

    @staticmethod
    def _decide(
        info: PermissionInfo, grants: EffectiveGrants, subject: UUID, resource: ResourceRef | None
    ) -> Decision:
        matching = [
            grant
            for grant in grants.for_permission(info.key)
            if scope_matches(grant.scope_kind, grant.scope_ref, subject, resource)
        ]
        confirm, sensitive = info.requires_confirmation, info.sensitive
        denies = [grant for grant in matching if grant.effect == "deny"]
        if denies:
            return Decision(False, "explicit_deny", denies[0].scope_kind, confirm, sensitive)
        if grants.is_admin:
            return Decision(True, "admin", "global", confirm, sensitive)
        if info.reserved:
            return Decision(False, "reserved", None, confirm, sensitive)
        allows = sorted(grant.scope_kind for grant in matching if grant.effect == "allow")
        if allows:
            return Decision(True, "granted", allows[0], confirm, sensitive)
        return Decision(False, "no_grant", None, confirm, sensitive)

    async def _permission(self, key: str) -> PermissionInfo | None:
        if request_memo() is None:  # a job, the CLI: the one permission
            await self.catalog.ensure()
            async with self.database.session() as session:
                row = await session.get(Permission, key)
            return _info(row) if row is not None else None
        return (await request_once("authz.permissions", self._catalog)).get(key)

    async def _catalog(self) -> dict[str, PermissionInfo]:
        """Issue 404: every permission at once, for the request (a page checks dozens of them)."""
        await self.catalog.ensure()
        async with self.database.session() as session:
            rows = (await session.execute(select(Permission))).scalars().all()
        return {row.key: _info(row) for row in rows}

    async def _grants(self, subject: UUID) -> EffectiveGrants:
        async def load() -> EffectiveGrants:
            async with self.database.session() as session:
                return await load_effective_grants(session, subject)

        return await request_once(("authz.grants", subject), load)

    async def visible(self, principal: Principal, permissions: Iterable[str]) -> set[str]:
        """Issue 404: which of ``permissions`` the principal holds, globally — to decide what a page *shows*
        (a palette's entries, a menu, a widget). Not an access decision, so not audited: the action itself is
        authorized (and audited) when it is called. One read of the catalog and the grants for all."""
        subject, _ = self._subject(principal)
        if subject is None:
            return set()
        wanted = set(permissions)
        catalog = await request_once("authz.permissions", self._catalog)
        grants = await self._grants(subject)
        held = set()
        for key in wanted:
            info = catalog.get(key)
            if info is not None and info.enabled and self._decide(info, grants, subject, None).allowed:
                held.add(key)
        if held and principal.channel == "ai":
            ai = catalog.get("ai.use")
            if ai is None or not self._decide(ai, grants, subject, None).allowed:
                return set()
        return held

    async def effective_permissions(self, principal: Principal) -> list[str]:
        """Enabled permissions the principal holds globally or for itself (UI hints, ``/me/permissions``)."""
        subject, _ = self._subject(principal)
        if subject is None:
            return []
        await self.catalog.ensure()
        async with self.database.session() as session:
            rows = (
                (await session.execute(select(Permission).where(Permission.enabled.is_(True))))
                .scalars()
                .all()
            )
        grants = await self._grants(subject)
        held = []
        for row in rows:
            info = PermissionInfo(
                row.key, row.enabled, row.sensitive, row.reserved, row.requires_confirmation
            )
            if self._decide(info, grants, subject, None).allowed:
                held.append(row.key)
        return sorted(held)

    # --- audit of sensitive decisions -----------------------------------------------------------------
    async def _audit(
        self,
        principal: Principal,
        permission: str,
        resource: ResourceRef | None,
        decision: Decision,
        context: dict[str, Any],
    ) -> None:
        memo = request_memo()
        memo_key = (
            "authz.audited",
            permission,
            resource.kind if resource else None,
            resource.id if resource else None,
        )
        if memo is not None and memo_key in memo:
            return
        entry = AuditRecord(
            action=f"authorize:{permission}",
            actor=principal if principal.is_authenticated else None,
            resource=resource,
            decision="allow" if decision.allowed else "deny",
            result="n/a",
            context={**context, "reason": decision.reason, "scope": decision.scope_matched},
            sensitive=True,
        )
        try:
            async with self.database.unit_of_work() as uow:
                await self.audit.record(uow.session, entry)
                if not decision.allowed:
                    metrics.increment("authz.sensitive_denials")
                    await self.events.publish(
                        uow.session,
                        "permission.denied",
                        {"permission": permission, "reason": decision.reason},
                        occurred_at=utc_now(self.clock),
                        actor=principal if principal.is_authenticated else None,
                        subject=SubjectRef(resource.kind, resource.id or "") if resource else None,
                        source="authz",
                    )
        except Exception as exc:
            raise AuditFailed("The action was refused because it could not be audited.") from exc
        if memo is not None:
            memo[memo_key] = True


def _info(row: Permission) -> PermissionInfo:
    return PermissionInfo(row.key, row.enabled, row.sensitive, row.reserved, row.requires_confirmation)
