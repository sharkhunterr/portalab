"""Spec 006 fixtures: Health on top of the Connectors harness (same capability registry, fake connector)."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from portalab.core.db import Database
from portalab.core.time import Clock
from portalab.modules.health.module import HealthModule
from portalab.modules.health.settings import HealthConfig
from tests.connectors_fixtures import ConnectorsHarness, make_connectors


@dataclass
class HealthHarness:
    cn: ConnectorsHarness
    module: HealthModule

    async def service(self, name: str = "Fake", *, base_url: str | None = None) -> str:
        return str(await self.cn.enabled(name, base_url=base_url))

    async def outbox(self, prefix: str) -> list[dict[str, Any]]:
        return await self.cn.outbox(prefix)


async def make_health(
    database: Database, blob_root: Path, clock: Clock | None = None, *, config: HealthConfig | None = None
) -> HealthHarness:
    cn = await make_connectors(database, blob_root, clock)
    module = HealthModule(
        database,
        cn.full.authz.engine.events,
        cn.full.authz.audit,
        cn.full.identity.capabilities,
        config=config or HealthConfig(unavailable_after_failures=2, section_timeout_seconds=0.5),
        clock=clock,
    )
    module.register_capabilities()
    return HealthHarness(cn, module)
