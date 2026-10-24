"""008 T023 — domain coverage checklist (FR-012): every listed domain registers a provider through the SDK
in the production wiring (#84 delivered the last ones — calendar, gamification and statistics — and named
the kinds community and marketplace answer to: ``member`` and ``product``).

The platform is wired in a child process: wiring fills process-wide registries (permissions, widgets,
consumers…), which no other test of this process must inherit."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

EXPECTED = {  # domain → the kind its provider answers to (owning spec)
    "navigation": "navigation",  # 008
    "services": "services",  # 008 over 005
    "users": "users",  # 002
    "media": "media",  # 024
    "wiki": "wiki",  # 011
    "news": "news",  # 011
    "tickets": "tickets",  # 016
    "community": "member",  # 012: members, by their display name
    "calendar": "calendar",  # 011
    "marketplace": "product",  # 015: the shop's products
    "statistics": "statistics",  # 017
    "gamification": "gamification",  # 013: achievements and quests
}

WIRE = """
import json, sys
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine
from portalab.app.wiring import wire_platform
from portalab.capabilities.catalog import new_registry
from portalab.core.db import Database

engine = create_async_engine("postgresql+asyncpg://wiring:only@127.0.0.1:9/never")  # never connected
platform = wire_platform(
    Database(engine), data_dir=Path(sys.argv[1]), capabilities=new_registry(), secret_key=bytes(32)
)
print(json.dumps(sorted(provider.kind for provider in platform.search.registry.providers())))
"""


@pytest.fixture(scope="module")
def kinds(tmp_path_factory: pytest.TempPathFactory) -> set[str]:
    data = tmp_path_factory.mktemp("wiring")
    done = subprocess.run(  # noqa: S603 — this interpreter, a fixed script
        [sys.executable, "-c", WIRE, str(data)],
        capture_output=True,
        text=True,
        timeout=180,
        cwd=Path(__file__).resolve().parents[3],
        check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    return set(json.loads(done.stdout.strip().splitlines()[-1]))


@pytest.mark.parametrize("domain", sorted(EXPECTED))
def test_domain_registers_a_provider(domain: str, kinds: set[str]) -> None:
    assert EXPECTED[domain] in kinds, f"{domain!r} registers no {EXPECTED[domain]!r} search provider"
