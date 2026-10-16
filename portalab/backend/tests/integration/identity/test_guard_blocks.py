"""028 (FR-039…FR-041): a member probing what they may not reach is blocked — the block stored, enforced by
every process and after a restart, lifted by an administrator or from the server's console."""

import io
from uuid import uuid4

import pytest

from portalab.core.db import Database
from portalab.modules.identity.guard import BlockStore, IntrusionGuard
from portalab.modules.identity.guard.cli import lift_blocks, list_blocks

pytestmark = pytest.mark.integration


async def test_a_block_outlives_the_process_and_the_console_lifts_it(database: Database) -> None:
    store = BlockStore(database)
    user = str(uuid4())
    await store.record("account", user, reason="refused on the administration", seconds=900, label="mallory")
    await store.record("address", "203.0.113.9", reason="attack-shaped address", seconds=900, points=64)
    # a new process (a restart) loads them
    fresh = IntrusionGuard()
    fresh.load(await store.active())
    assert fresh.user_blocked(user) is not None and fresh.blocked(["ip:203.0.113.9"]) is not None
    out = io.StringIO()
    assert await list_blocks(database, out=out) == 0
    assert "mallory" in out.getvalue() and "203.0.113.9" in out.getvalue()
    audited: list[tuple[str, dict[str, object]]] = []

    async def audit(action: str, context: dict[str, object]) -> None:
        audited.append((action, context))

    # the Admin's own block (any block) lifted from the console, by login
    assert await lift_blocks(database, "mallory", everything=False, audit=audit, out=io.StringIO()) == 0
    assert audited[0][0] == "security.block_lifted" and str(audited[0][1]["by"]).startswith("console:")
    fresh.load(await store.active())
    assert fresh.user_blocked(user) is None and fresh.blocked(["ip:203.0.113.9"]) is not None
    assert await lift_blocks(database, None, everything=True, out=io.StringIO()) == 0
    fresh.load(await store.active())
    assert fresh.blocked(["ip:203.0.113.9"]) is None
    assert await lift_blocks(database, "nobody", everything=False, out=io.StringIO()) == 1
