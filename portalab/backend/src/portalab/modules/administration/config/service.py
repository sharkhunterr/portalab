"""``ConfigService`` (T009, T013): the single configuration store (CD-011) — capability ``admin.config``.

* reads resolve code default ▸ global ▸ module ▸ plugin ▸ user within policy (pure :func:`resolve`);
* stored values are upgraded to the declared schema version and validated on read; an invalid stored value
  falls back to the next scope / the code default and is counted (never a crash, never a silent reset);
* sensitive values are encrypted with the application key (``core.secrets``) and never returned by the API;
* every change writes ``config.setting_history`` (redacted), publishes ``admin.config_changed`` and, for
  admin changes, an audit record — in one transaction. ``apply`` is idempotent per ``change_id``.
"""

import hashlib
import json
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Mapping
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.config import EffectiveValue
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authorization import request_memo
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.config_declaration import SettingDeclaration, SettingDeclarationError
from portalab.core.db import Database
from portalab.core.errors import Conflict, ValidationFailed
from portalab.core.event_port import EventPublisher
from portalab.core.ids import new_id
from portalab.core.logging import MASK, redact
from portalab.core.secrets import SecretBox
from portalab.core.time import Clock, utc_now
from portalab.modules.administration.config.registry import (
    SettingRegistry,
    allowed_scopes,
    is_user_overridable,
)
from portalab.modules.administration.config.resolution import MISSING, PolicyView, resolve, within_bounds
from portalab.modules.administration.models import Policy, Setting, SettingHistory
from portalab.modules.administration.observability import log, metrics

ChangeListener = Callable[[set[str]], Awaitable[None]]


class InvalidSettingValue(ValidationFailed):
    default_code = "admin.invalid_value"
    default_title = "Invalid setting value"


class ScopeNotAllowed(ValidationFailed):
    default_code = "admin.scope_not_allowed"
    default_title = "This setting cannot be set at this scope"


class OutOfBounds(ValidationFailed):
    default_code = "admin.out_of_bounds"
    default_title = "Value outside the administrator's bounds"


# the settings read once for a refresh (``ConfigService.read_at_once``): rows by key, policies by key —
# emptied when it ends, so a task started meanwhile (which inherits it) reads the database again
_SNAPSHOT: ContextVar[dict[str, Any] | None] = ContextVar("config_snapshot", default=None)


@dataclass(frozen=True, slots=True)
class Change:
    key: str
    value: Any
    scope: str = "global"
    scope_ref: str = ""
    unset: bool = False


@dataclass
class Preview:
    diff: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _ref_hash(scope: str, scope_ref: str) -> str:
    return hashlib.sha256(scope_ref.encode()).hexdigest() if scope == "user" else scope_ref


class ConfigService:
    def __init__(
        self,
        database: Database,
        registry: SettingRegistry,
        secrets: SecretBox,
        audit: AuditSink,
        events: EventPublisher,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.registry = registry
        self.secrets = secrets
        self.audit = audit
        self.events = events
        self.clock = clock
        self._listeners: list[tuple[str, ChangeListener]] = []

    # --- listeners (in-process consumers refresh their snapshot, e.g. identity.* keys) -------------------
    def on_change(self, prefix: str, listener: ChangeListener) -> None:
        self._listeners.append((prefix, listener))

    async def _notify(self, keys: set[str]) -> None:
        for prefix, listener in self._listeners:
            matching = {key for key in keys if key.startswith(prefix)}
            if matching:
                try:
                    await listener(matching)
                except Exception:
                    log.exception("configuration listener failed")

    # --- storage encoding --------------------------------------------------------------------------------
    def _encode(self, declaration: SettingDeclaration, value: Any) -> Any:
        if declaration.sensitive:
            return {"enc": self.secrets.encrypt(json.dumps(value), context=f"config:{declaration.key}")}
        return value

    def decode(self, declaration: SettingDeclaration, row: Setting) -> Any:
        """Stored → typed value of the current schema version, or MISSING when unusable."""
        try:
            raw = row.value
            if declaration.sensitive:
                raw = json.loads(
                    self.secrets.decrypt(raw["enc"], context=f"config:{declaration.key}").reveal()
                )
            if row.schema_version < declaration.version:
                raw = self.registry.upgrade(declaration.key, raw, row.schema_version, declaration.version)
            return declaration.validate(raw)
        except Exception:
            metrics.increment("admin.config.invalid_stored_values")
            log.warning("invalid stored setting ignored", extra={"fields": {"setting": declaration.key}})
            return MISSING

    def redacted(self, declaration: SettingDeclaration, value: Any) -> Any:
        if value is MISSING or value is None:
            return None
        return MASK if declaration.sensitive else redact(value, key=declaration.key)

    # --- reads -------------------------------------------------------------------------------------------
    @asynccontextmanager
    async def read_at_once(self) -> AsyncIterator[None]:
        """Every global, module and plugin setting and every policy read at once, the reads inside answered
        from them — a refresh of every module's configuration in two queries instead of one per setting (a
        user's own value is still read as it is asked)."""
        async with self.database.session() as session:
            rows = (await session.execute(select(Setting).where(Setting.scope != "user"))).scalars().all()
            policies = (await session.execute(select(Policy).where(Policy.removed_at.is_(None)))).scalars()
            by_policy = {policy.key: policy for policy in policies}
        by_key: dict[str, list[Setting]] = {}
        for row in rows:
            by_key.setdefault(row.key, []).append(row)
        snapshot: dict[str, Any] = {"rows": by_key, "policies": by_policy}
        token = _SNAPSHOT.set(snapshot)
        try:
            yield
        finally:
            snapshot.clear()
            _SNAPSHOT.reset(token)

    async def _rows(self, session: AsyncSession, key: str) -> list[Setting]:
        memo = request_memo()
        cache_key = ("admin.config.rows", key)
        if memo is not None and cache_key in memo:
            return memo[cache_key]  # type: ignore[no-any-return]
        rows = list((await session.execute(select(Setting).where(Setting.key == key))).scalars())
        if memo is not None:
            memo[cache_key] = rows
        return rows

    async def _policy(self, session: AsyncSession, key: str) -> Policy | None:
        return (
            await session.execute(select(Policy).where(Policy.key == key, Policy.removed_at.is_(None)))
        ).scalar_one_or_none()

    async def get(
        self, key: str, *, user_id: UUID | None = None, module: str | None = None, plugin: str | None = None
    ) -> EffectiveValue:
        declaration = self.registry.declaration(key)
        snapshot = _SNAPSHOT.get()
        if snapshot and user_id is None:
            rows, policy = snapshot["rows"].get(key, []), snapshot["policies"].get(key)
        else:
            async with self.database.session() as session:
                rows = await self._rows(session, key)
                policy = await self._policy(session, key)
        wanted = {
            "global": "",
            "module": module
            or (declaration.owner.removeprefix("module:") if declaration.scope == "module" else None),
            "plugin": plugin
            or (declaration.owner.removeprefix("plugin:") if declaration.scope == "plugin" else None),
            "user": str(user_id) if user_id else None,
        }
        stored: dict[str, Any] = {}
        for row in rows:
            if wanted.get(row.scope) is not None and row.scope_ref == wanted[row.scope]:
                stored[row.scope] = self.decode(declaration, row)
        view = PolicyView(policy.mode, policy.bounds) if policy else None
        return resolve(
            key,
            declaration.default,
            stored,
            user_overridable=is_user_overridable(declaration),
            policy=view,
        )

    async def stored_value(self, key: str, scope: str, scope_ref: str) -> Any:
        declaration = self.registry.declaration(key)
        async with self.database.session() as session:
            row = (
                await session.execute(
                    select(Setting).where(
                        Setting.key == key, Setting.scope == scope, Setting.scope_ref == scope_ref
                    )
                )
            ).scalar_one_or_none()
        return self.decode(declaration, row) if row is not None else MISSING

    # --- validation & preview ---------------------------------------------------------------------------
    async def _check(self, session: AsyncSession, change: Change) -> tuple[SettingDeclaration, Any]:
        declaration = self.registry.declaration(change.key)
        if change.scope not in allowed_scopes(declaration):
            raise ScopeNotAllowed(f"{change.key} cannot be set at the {change.scope} scope.")
        if change.scope in ("module", "plugin", "user") and not change.scope_ref:
            raise ScopeNotAllowed("This scope needs a reference.")
        if change.unset:
            return declaration, MISSING
        try:
            value = declaration.validate(change.value)
        except SettingDeclarationError as exc:
            raise InvalidSettingValue(
                f"Invalid value for {change.key}.", extensions={"setting": change.key}
            ) from exc
        problems = await self.registry.dynamic_errors(
            change.key, value, user_ref=change.scope_ref if change.scope == "user" else None
        )
        if problems:
            raise InvalidSettingValue("; ".join(problems), extensions={"setting": change.key})
        if change.scope == "user":
            policy = await self._policy(session, change.key)
            if policy is not None and policy.mode == "bound" and not within_bounds(value, policy.bounds):
                raise OutOfBounds(
                    "This value is outside the allowed range.", extensions={"bounds": policy.bounds}
                )
        return declaration, value

    async def validate(self, changes: Iterable[Change]) -> Preview:
        """Diff, warnings and errors without any side effect (T013)."""
        preview = Preview()
        async with self.database.session() as session:
            for change in changes:
                try:
                    declaration, value = await self._check(session, change)
                except (ValidationFailed, Conflict) as exc:
                    preview.errors.append({"key": change.key, "code": exc.code, "detail": exc.detail})
                    continue
                before = await self.stored_value(change.key, change.scope, change.scope_ref)
                preview.diff.append(
                    {
                        "key": change.key,
                        "scope": change.scope,
                        "before": self.redacted(declaration, before),
                        "after": self.redacted(declaration, value),
                    }
                )
                if declaration.sensitive:
                    preview.warnings.append(f"{change.key} is sensitive: its value is write-only.")
                if (await self._policy(session, change.key)) is not None and change.scope == "global":
                    preview.warnings.append(f"{change.key} is constrained by an administrator policy.")
        return preview

    # --- writes ------------------------------------------------------------------------------------------
    async def apply(
        self,
        changes: Iterable[Change],
        actor: Principal,
        *,
        change_id: str | None = None,
        reason: str = "",
        admin_change: bool = True,
    ) -> bool:
        """Apply all changes atomically; returns False when ``change_id`` was already applied (idempotent)."""
        items = list(changes)
        now = utc_now(self.clock)
        change_id = change_id or str(new_id())  # retries reuse the caller's Idempotency-Key
        keys = {change.key for change in items}
        async with self.database.unit_of_work() as uow:
            session = uow.session
            published = await self.events.publish(
                session,
                "admin.config_changed",
                {"keys": sorted(keys), "change_id": change_id},
                occurred_at=now,
                actor=actor,
                source="administration",
                dedup_key=f"admin.config_changed:{change_id}",
            )
            if published.duplicate:
                return False
            # a missing row cannot be locked FOR UPDATE: two first writes of the same setting would both
            # insert (unique violation). Serialize per setting with transaction-scoped advisory locks, taken
            # in a fixed order so concurrent multi-key changes cannot deadlock.
            for lock in sorted({f"{c.key}|{c.scope}|{c.scope_ref}" for c in items}):
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:lock, 0))"), {"lock": lock}
                )
            for change in items:
                declaration, value = await self._check(session, change)
                existing = (
                    await session.execute(
                        select(Setting)
                        .where(
                            Setting.key == change.key,
                            Setting.scope == change.scope,
                            Setting.scope_ref == change.scope_ref,
                        )
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                before = self.decode(declaration, existing) if existing is not None else MISSING
                if value is MISSING:
                    if existing is not None:
                        await session.delete(existing)
                elif existing is None:
                    session.add(
                        Setting(
                            key=change.key,
                            scope=change.scope,
                            scope_ref=change.scope_ref,
                            value=self._encode(declaration, value),
                            schema_version=declaration.version,
                            updated_by=actor.user_id,
                            updated_at=now,
                        )
                    )
                else:
                    existing.value = self._encode(declaration, value)
                    existing.schema_version = declaration.version
                    existing.updated_by = actor.user_id
                    existing.updated_at = now
                session.add(
                    SettingHistory(
                        key=change.key,
                        scope=change.scope,
                        scope_ref_hash=_ref_hash(change.scope, change.scope_ref),
                        old_value_redacted=self.redacted(declaration, before),
                        new_value_redacted=self.redacted(declaration, value),
                        actor_id=actor.user_id,
                        changed_at=now,
                        reason=reason[:256],
                    )
                )
                if admin_change:
                    await self.audit.record(
                        session,
                        AuditRecord(
                            action="admin.config_changed",
                            actor=actor,
                            resource=ResourceRef("setting", change.key),
                            decision="allow",
                            result="success",
                            context={
                                "scope": change.scope,
                                "old": self.redacted(declaration, before),
                                "new": self.redacted(declaration, value),
                                "change_id": change_id,
                            },
                            sensitive=True,
                        ),
                    )
            await session.flush()
        memo = request_memo()
        if memo is not None:
            for key in keys:
                memo.pop(("admin.config.rows", key), None)
        metrics.increment("admin.config.changes", len(items))
        await self._notify(keys)
        return True

    async def set(
        self,
        key: str,
        value: Any,
        *,
        scope: str = "global",
        scope_ref: str = "",
        actor: Principal,
        reason: str = "",
    ) -> None:
        await self.apply(
            [Change(key, value, scope, scope_ref)], actor, reason=reason, admin_change=scope != "user"
        )

    async def snapshot(self, keys: Iterable[str]) -> Mapping[str, Any]:
        return {key: (await self.get(key)).value for key in keys}

    async def delete_user_values(self, session: AsyncSession, user_id: UUID) -> int:
        result = await session.execute(
            delete(Setting).where(Setting.scope == "user", Setting.scope_ref == str(user_id))
        )
        return int(getattr(result, "rowcount", 0) or 0)
