"""Theme registry (T014, T027, T037, T042): validate → accessibility floor → persist; enable/disable (never
delete); policy-filtered catalog for users. Registrations are owner-tagged (``module:<id>``,
``plugin:<key>``, ``marketplace:<product>``) so all of an owner's themes can be withdrawn at once.
Enabling an external (marketplace) theme is a sensitive, audited action."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import select

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound, ValidationFailed
from portalab.core.time import Clock, utc_now
from portalab.modules.ui.models import Theme
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
            "allowedThemes": list(
                await self._setting("ui.allowedThemes", ["light", "dark", "high-contrast"])
            ),
            "defaultTheme": await self._setting("ui.defaultTheme", "light"),
            "textScaleMin": await self._setting("ui.textScale.min", 0.85),
            "textScaleMax": await self._setting("ui.textScale.max", 2.0),
            "forceReducedMotion": await self._setting("ui.forceReducedMotion", False),
        }

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
                if not enabled and key == await self._setting("ui.defaultTheme", "light"):
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

    async def get(self, key: str) -> Theme:
        async with self.database.session() as session:
            row = (await session.execute(select(Theme).where(Theme.key == key))).scalar_one_or_none()
        if row is None:
            raise ThemeNotFound("No such theme.")
        return row

    async def all(self) -> list[Theme]:
        async with self.database.session() as session:
            return list((await session.execute(select(Theme).order_by(Theme.key))).scalars())

    async def catalog(self) -> dict[str, Any]:
        """What a user may choose: enabled themes allowed by policy (+ accessibility themes)."""
        policy = await self.policy()
        allowed = set(policy["allowedThemes"]) | set(ACCESSIBILITY_THEMES)
        themes = [theme_out(row) for row in await self.all() if row.enabled and row.key in allowed]
        return {"themes": themes, "policy": policy}

    async def choice_errors(self, value: Any) -> list[str]:
        """Dynamic validator of the ``ui.theme`` preference."""
        if value is None:
            return []
        catalog = await self.catalog()
        if value not in {theme["key"] for theme in catalog["themes"]}:
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
