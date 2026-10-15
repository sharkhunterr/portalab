"""Theme registry (T014, T027, T037, T042): validate → accessibility floor → persist; enable/disable (never
delete); policy-filtered catalog for users. Registrations are owner-tagged (``module:<id>``,
``plugin:<key>``, ``marketplace:<product>``) so all of an owner's themes can be withdrawn at once.
Enabling an external (marketplace) theme is a sensitive, audited action."""

import asyncio
import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.themes import COSMETICS
from portalab.capabilities.themes import ENTITLEMENTS as THEME_ENTITLEMENTS
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound, ValidationFailed
from portalab.core.time import Clock, utc_now
from portalab.modules.ui.models import Theme
from portalab.modules.ui.settings import BUILTIN_KEYS, DEFAULT_THEME
from portalab.modules.ui.themes.definition import floor_report, validate_definition

ACCESSIBILITY_THEMES = ("high-contrast",)  # always offered: an accessibility preference, not a style choice


class InvalidTheme(ValidationFailed):
    default_code = "theme.invalid_definition"
    default_title = "Invalid theme definition"


class FloorViolation(ValidationFailed):
    default_code = "theme.floor_violation"
    default_title = "The theme fails the accessibility floor"


class ThemeNotFound(NotFound):
    default_code = "theme.not_found"


class ThemeConflict(Conflict):
    default_code = "theme.conflict"


def theme_out(row: Theme, *, admin: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {
        "key": row.key,
        "name": row.name,
        "colorScheme": row.definition.get("colorScheme"),
        "family": row.definition.get("family"),
        "definition": row.definition,
        "version": row.version,
    }
    if admin:
        out |= {
            "source": row.source,
            "owner": row.owner,
            "enabled": row.enabled,
            "floor_ok": row.floor_report.get("ok"),
        }
    return out


class ThemeService:
    def __init__(
        self,
        database: Database,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.audit = audit
        self.capabilities = capabilities
        self.clock = clock

    async def _setting(self, key: str, fallback: Any) -> Any:
        providers = self.capabilities.system_providers(CONFIG)
        if not providers:
            return fallback
        try:
            return (await providers[0].provider.get(key)).value
        except Exception:
            return fallback

    async def policy(self) -> dict[str, Any]:
        return {
            "allowedThemes": await self._allowed(),
            "defaultTheme": await self._setting("ui.defaultTheme", DEFAULT_THEME),
            "textScaleMin": await self._setting("ui.textScale.min", 0.85),
            "textScaleMax": await self._setting("ui.textScale.max", 2.0),
            "forceReducedMotion": await self._setting("ui.forceReducedMotion", False),
        }

    async def _allowed(self) -> list[str]:
        """The themes the policy allows, and (issue 1) the interfaces of a visual pack, switched on."""
        allowed = list(await self._setting("ui.allowedThemes", list(BUILTIN_KEYS)))
        imported = [
            row.key for row in await self.all() if row.enabled and str(row.source).startswith("visuals:")
        ]
        return [*allowed, *(key for key in imported if key not in allowed)]

    def check(self, document: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        theme, errors = validate_definition(document)
        if theme is None:
            raise InvalidTheme("The theme definition is invalid.", extensions={"errors": errors[:50]})
        report = floor_report(theme)
        if not report["ok"]:
            raise FloorViolation(
                "The theme fails the accessibility floor.", extensions={"violations": report["violations"]}
            )
        return theme.model_dump(mode="json", by_alias=True, exclude_none=True), report

    async def _audit(
        self, session: Any, actor: Principal, action: str, row: Theme, *, sensitive: bool
    ) -> None:
        await self.audit.record(
            session,
            AuditRecord(
                action=action,
                actor=actor,
                resource=ResourceRef("theme", row.key),
                decision="allow",
                result="success",
                context={"source": row.source, "enabled": row.enabled, "version": row.version},
                sensitive=sensitive,
            ),
        )

    async def register(
        self, actor: Principal, document: Mapping[str, Any], *, source: str = "admin", owner: str = "core"
    ) -> dict[str, Any]:
        definition, report = self.check(document)
        now = utc_now(self.clock)
        external = not source.startswith(("admin", "builtin"))
        async with self.database.unit_of_work() as uow:
            existing = (
                await uow.session.execute(select(Theme).where(Theme.key == definition["key"]))
            ).scalar_one_or_none()
            if existing is not None:
                raise ThemeConflict("A theme with this key already exists; update it instead.")
            row = Theme(
                key=definition["key"],
                name=definition["name"],
                source=source,
                owner=owner,
                definition=definition,
                schema_version=definition["schemaVersion"],
                version=1,
                enabled=not external,  # external themes are enabled explicitly (sensitive)
                floor_report=report,
                created_at=now,
                updated_at=now,
            )
            uow.session.add(row)
            await uow.session.flush()
            await self._audit(uow.session, actor, "theme.registered", row, sensitive=external)
            return theme_out(row, admin=True)

    async def update(
        self,
        actor: Principal,
        key: str,
        *,
        definition: Mapping[str, Any] | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        async with self.database.unit_of_work() as uow:
            row = (
                await uow.session.execute(select(Theme).where(Theme.key == key).with_for_update())
            ).scalar_one_or_none()
            if row is None:
                raise ThemeNotFound("No such theme.")
            if definition is not None:
                if row.source == "builtin":
                    raise ThemeConflict("Built-in themes cannot be edited; register a new theme instead.")
                clean, report = self.check({**definition, "key": key})
                row.definition, row.floor_report, row.name = clean, report, clean["name"]
                row.version += 1
            if enabled is not None and enabled != row.enabled:
                default = await self._setting("ui.defaultTheme", DEFAULT_THEME)
                if not enabled and default in (key, row.definition.get("family")):  # family default (027)
                    raise ThemeConflict(
                        "The portal default theme cannot be disabled; change the default first."
                    )
                if enabled and not row.floor_report.get("ok", False):
                    raise FloorViolation("The theme fails the accessibility floor.")
                row.enabled = enabled
            row.updated_at = utc_now(self.clock)
            external = not row.source.startswith(("admin", "builtin"))
            await self._audit(
                uow.session, actor, "theme.updated", row, sensitive=external or enabled is not None
            )
            return theme_out(row, admin=True)

    async def sync_builtin(self, directory: Path) -> int:
        documents = await asyncio.to_thread(
            lambda: [json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("*.json"))]
        )
        return await self._sync_builtin(documents)

    async def _sync_builtin(self, documents: list[Any]) -> int:
        """027: built-in themes follow the files shipped with the portal — a built-in row whose definition
        differs from its file is updated (version bumped); new files are registered. Returns the changes."""
        changed = 0
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            rows = {
                row.key: row
                for row in (
                    await uow.session.execute(select(Theme).where(Theme.source == "builtin"))
                ).scalars()
            }
            for document in documents:
                definition, report = self.check(document)
                row = rows.get(definition["key"])
                if row is None:
                    if await uow.session.scalar(select(Theme.id).where(Theme.key == definition["key"])):
                        continue  # a non-built-in theme owns the key
                    uow.session.add(
                        Theme(
                            key=definition["key"],
                            name=definition["name"],
                            source="builtin",
                            owner="core",
                            definition=definition,
                            schema_version=definition["schemaVersion"],
                            version=1,
                            enabled=True,
                            floor_report=report,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    changed += 1
                elif row.definition != definition or row.name != definition["name"]:
                    row.definition, row.floor_report, row.name = definition, report, definition["name"]
                    row.version += 1
                    row.updated_at = now
                    changed += 1
        return changed

    async def get(self, key: str) -> Theme:
        async with self.database.session() as session:
            row = (await session.execute(select(Theme).where(Theme.key == key))).scalar_one_or_none()
        if row is None:
            raise ThemeNotFound("No such theme.")
        return row

    async def all(self) -> list[Theme]:
        async with self.database.session() as session:
            return list((await session.execute(select(Theme).order_by(Theme.key))).scalars())

    async def catalog(self, user_id: UUID | None = None) -> dict[str, Any]:
        """What a user may choose: enabled themes allowed by policy (+ accessibility themes). With a user,
        a theme sold in the Marketplace is offered only to its owners (027 US11) — never the portal default
        (or its family) nor an accessibility theme."""
        policy = await self.policy()
        allowed = set(policy["allowedThemes"]) | set(ACCESSIBILITY_THEMES)
        themes = [theme_out(row) for row in await self.all() if row.enabled and row.key in allowed]
        if user_id is None:
            return {"themes": themes, "policy": policy}
        locked = await self._locked_for(user_id, policy["defaultTheme"])
        sold = await self._sold()
        for theme in themes:  # #72: a theme sold in the shop shows its rarity (by its key or its family)
            detail = sold.get(theme["key"]) or sold.get(theme.get("family") or "")
            if detail:
                theme.update(rarity=detail.get("rarity"), price=detail.get("price"))
        return {
            "themes": [theme for theme in themes if theme["key"] not in locked],
            "locked": [theme for theme in themes if theme["key"] in locked],  # shown as "in the shop"
            "policy": policy,
        }

    async def _sold(self) -> dict[str, dict[str, Any]]:
        """The product selling each theme (rarity, price), when the Marketplace says (#72)."""
        try:
            providers = self.capabilities.system_providers(COSMETICS)
        except Exception:
            return {}
        details = getattr(providers[0].provider, "details", None) if providers else None
        if details is None:
            return {}
        try:
            result: dict[str, dict[str, Any]] = await details("theme", "theme")
        except Exception:
            return {}
        return result

    async def _locked_for(self, user_id: UUID, default: str) -> frozenset[str]:
        providers = self.capabilities.system_providers(THEME_ENTITLEMENTS)
        if not providers:
            return frozenset()
        entitlements = providers[0].provider
        sold = await entitlements.sold()
        if not sold:
            return frozenset()
        free = {default, *ACCESSIBILITY_THEMES}
        return frozenset(sold - await entitlements.owned(user_id) - free)

    async def allowed_keys(self) -> frozenset[str]:
        """``ui.theme_catalog``: enabled themes the policy allows (campaign overlays, 014)."""
        return frozenset(theme["key"] for theme in (await self.catalog())["themes"])

    async def choice_errors(self, value: Any, user_ref: str | None = None) -> list[str]:
        """Dynamic validator of the ``ui.theme`` preference (per user: sold themes need ownership)."""
        if value is None:
            return []
        user_id = None
        if user_ref:
            try:
                user_id = UUID(user_ref)
            except ValueError:
                user_id = None
        catalog = await self.catalog(user_id)
        choices = {theme["key"] for theme in catalog["themes"]}
        choices |= {theme["family"] for theme in catalog["themes"] if theme.get("family")}  # 027 R8
        if value not in choices:
            return [f"theme {value!r} is not available"]
        return []

    async def unregister(self, owner: str, *, at: datetime | None = None) -> int:
        """Withdraw every theme of an owner (disabled, kept: preferences may still reference them)."""
        async with self.database.unit_of_work() as uow:
            rows = (
                (await uow.session.execute(select(Theme).where(Theme.owner == owner, Theme.enabled)))
                .scalars()
                .all()
            )
            for row in rows:
                row.enabled = False
                row.updated_at = at or utc_now(self.clock)
            return len(rows)
