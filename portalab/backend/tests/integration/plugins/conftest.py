"""Plugin integration fixtures: the plugins module on the real database and event store with isolated
registries (fresh per test), a unique PostgreSQL role prefix per test (roles are cluster-wide), a package
root in a temporary directory, the real 026 plugin catalogs and an in-memory theme registry, and helpers
to write packages (manifest, code, migrations)."""

import contextlib
import shutil
import sys
import textwrap
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI

from portalab.capabilities.ai import AIToolRegistry
from portalab.capabilities.automation_actions import ActionRegistry
from portalab.capabilities.community import SectionRegistry, ShelfRegistry
from portalab.capabilities.connector_sdk import ConnectorRegistry
from portalab.capabilities.content import CalendarSourceRegistry
from portalab.capabilities.dashboard import WidgetRegistry
from portalab.capabilities.marketplace import ProductTypeRegistry
from portalab.capabilities.media_core import MediaTypeRegistry
from portalab.capabilities.navigation.registry import NavigationRegistry
from portalab.capabilities.notifications import CategoryRegistry
from portalab.capabilities.observability import ObservableRegistry
from portalab.capabilities.plugins import I18N_CATALOGS, THEME_REGISTRY
from portalab.capabilities.search import SearchRegistry
from portalab.capabilities.statistics import PackRegistry
from portalab.core.authz_port import Principal
from portalab.core.config_declaration import SettingCatalog
from portalab.core.db import Database
from portalab.core.errors import NotFound
from portalab.core.secrets import SecretBox
from portalab.core.time import FixedClock
from portalab.modules.i18n.catalog.plugins import PluginCatalogs
from portalab.modules.plugins.context.registries import Registries
from portalab.modules.plugins.module import PluginsModule
from tests.events_fixtures import EventsHarness, make_events
from tests.integration.privacy.conftest import NOW

HELLO = Path(__file__).resolve().parents[4] / "examples" / "plugins" / "hello"
SYSTEM = Principal(channel="system")


@dataclass
class Themes:
    """022 as the plugin manager sees it."""

    themes: dict[str, dict[str, Any]] = field(default_factory=dict)

    async def register(
        self, actor: Principal, document: Mapping[str, Any], *, source: str = "admin", owner: str = "core"
    ) -> dict[str, Any]:
        self.themes[str(document["key"])] = {"owner": owner, "enabled": True, **document}
        return dict(document)

    async def update(
        self,
        actor: Principal,
        key: str,
        *,
        definition: Mapping[str, Any] | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        if key not in self.themes:
            raise NotFound("No such theme.")
        if enabled is not None:
            self.themes[key]["enabled"] = enabled
        return self.themes[key]

    async def unregister(self, owner: str) -> int:
        live = [k for k, t in self.themes.items() if t["owner"] == owner and t["enabled"]]
        for key in live:
            self.themes[key]["enabled"] = False
        return len(live)


@dataclass
class PlHarness:
    ev: EventsHarness
    module: PluginsModule
    clock: FixedClock
    root: Path
    themes: Themes
    catalogs: PluginCatalogs
    people: dict[str, UUID] = field(default_factory=dict)

    @property
    def database(self) -> Database:
        return self.ev.full.database

    @property
    def registries(self) -> Registries:
        return self.module.registries

    def p(self, name: str) -> Principal:
        return Principal(user_id=self.people[name])

    def package(
        self,
        key: str,
        version: str = "1.0.0",
        *,
        manifest: Mapping[str, Any] | None = None,
        code: str | None = None,
        migrations: Mapping[str, str] | None = None,
        extra: str = "",
    ) -> Path:
        """Write ``available/<key>-<version>/`` with a manifest (TOML), optional code and migrations."""
        target = self.root / "available" / f"{key}-{version}"
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        lines = [f'key = "{key}"', f'name = "{key.title()}"', f'version = "{version}"']
        for name, value in (manifest or {}).items():
            lines.append(f"{name} = {toml(value)}")
        if code is not None:
            lines.append(f'entry_point = "{key}_plugin:register"')
            package = target / f"{key}_plugin"
            package.mkdir()
            (package / "__init__.py").write_text(textwrap.dedent(code), encoding="utf-8")
        if migrations:
            lines.append('migrations = "migrations"')
            folder = target / "migrations"
            folder.mkdir()
            for name, sql in migrations.items():
                (folder / name).write_text(sql, encoding="utf-8")
        (target / "plugin.toml").write_text("\n".join(lines) + "\n" + extra, encoding="utf-8")
        return target

    def hello(self) -> Path:
        target = self.root / "available" / "hello"
        if not target.exists():
            shutil.copytree(HELLO, target, ignore=shutil.ignore_patterns("__pycache__"))
        return target

    async def installed(self, source: Path, *, enable: bool = True, restart: bool = True) -> str:
        plugin, _ = await self.module.lifecycle.install(SYSTEM, source)
        await self.module.lifecycle.approve(SYSTEM, plugin.key)
        if enable:
            await self.module.lifecycle.enable(SYSTEM, plugin.key)
            if restart:
                await self.module.lifecycle.load_enabled()
        return plugin.key


def toml(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(toml(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f'"{k}" = {toml(v)}' for k, v in value.items()) + " }"
    raise TypeError(type(value))


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
async def harness(database: Database, tmp_path: Path, clock: FixedClock) -> AsyncIterator[PlHarness]:
    ev = make_events(database, tmp_path / "blobs", clock)
    ev.module.register()
    capabilities = ev.full.identity.capabilities
    catalogs, themes = PluginCatalogs(), Themes()
    capabilities.provide(I18N_CATALOGS, catalogs, instance_ref="test026", owner="module:test")
    capabilities.provide(THEME_REGISTRY, themes, instance_ref="test022", owner="module:test")
    registries = Registries(
        capabilities,
        navigation=NavigationRegistry(),
        widgets=WidgetRegistry(),
        search=SearchRegistry(),
        calendar=CalendarSourceRegistry(),
        packs=PackRegistry(),
        actions=ActionRegistry(),
        ai_tools=AIToolRegistry(),
        categories=CategoryRegistry(),
        settings=SettingCatalog(),
        event_types=ev.types,
        consumers=ev.consumers,
        product_types=ProductTypeRegistry(),
        media_types=MediaTypeRegistry(),
        sections=SectionRegistry(),
        shelves=ShelfRegistry(),
        connectors=ConnectorRegistry(),
        observables=ObservableRegistry(),
    )
    root = tmp_path / "plugins"
    (root / "available").mkdir(parents=True)
    module = PluginsModule(
        database,
        ev.publisher,
        ev.full.authz.audit,
        capabilities,
        ev.full.authz.engine,
        clock=clock,
        root=root,
        role_prefix=f"plugin_{uuid4().hex[:8]}_",
        registries=registries,
        secret_box=SecretBox(b"t" * 32),
    )
    module.register()
    # spec 023's suites exercise in-process code plugins: an install that allows them (030, FR-020a)
    module.config = replace(module.config, unconfined="allow")
    await ev.full.authz.catalog.sync()
    harness = PlHarness(ev, module, clock, root, themes, catalogs)
    yield harness
    await module.runtime.stop_all()  # 030: confined plugins' processes
    for plugin in await module.lifecycle.all():  # roles are cluster-wide: drop them
        with contextlib.suppress(Exception):
            await module.storage.drop(plugin.key)
    for name, loaded in list(sys.modules.items()):  # a "restart" between tests: forget plugin code
        origin = getattr(loaded, "__file__", None)
        if origin and str(root) in origin:
            del sys.modules[name]


@pytest.fixture
def app(harness: PlHarness, heads: set[str]) -> FastAPI:
    from portalab.app.main import create_app

    full = harness.ev.full
    return create_app(
        database=full.database,
        migration_heads=heads,
        identity=full.identity,
        authz=full.authz,
        privacy=full.privacy,
        administration=full.administration,
        plugins=harness.module,
        static_dir=None,
    )


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as http:
        yield http


@pytest.fixture
async def pl(harness: PlHarness, app: FastAPI) -> PlHarness:
    """``boss`` (admin), ``ursula`` and ``ulrich`` (users)."""
    from tests.authz_fixtures import make_admin
    from tests.integration.identity.helpers import create_user, module_of

    harness.people = {name: await create_user(module_of(app), name) for name in ("boss", "ursula", "ulrich")}
    await make_admin(harness.ev.full, harness.people["boss"])
    return harness
