"""``portalab security blocks list|lift`` (spec 028 FR-040a): the intrusion guard's blocks, from the server's
console — no sign-in, the Admin's own block included. Running processes follow within seconds."""

import getpass
import sys
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from portalab.core.db import Database
from portalab.modules.identity.guard.store import BlockStore

Audit = Callable[[str, dict[str, Any]], Awaitable[None]]


def console_user() -> str:
    try:
        return f"console:{getpass.getuser()}"
    except Exception:  # no login name (a container without a passwd entry)
        return "console:unknown"


async def list_blocks(database: Database, out: Any = sys.stdout) -> int:
    rows = await BlockStore(database).active()
    if not rows:
        out.write("no block in force\n")
        return 0
    now = datetime.now(UTC)
    for row in rows:
        minutes = max(0, round((row.until - now).total_seconds() / 60))
        who = row.label or row.subject
        out.write(
            f"{row.id}  {row.kind:<8} {who:<32} {row.reason:<32} {row.points:>4} pts  {minutes} min left\n"
        )
    return 0


async def lift_blocks(
    database: Database,
    target: str | None,
    *,
    everything: bool,
    audit: Audit | None = None,
    out: Any = sys.stdout,
) -> int:
    """``target``: a block's id, or a login, user id or address (its blocks); ``everything``: all of them."""
    store = BlockStore(database)
    by = console_user()
    if everything:
        lifted = await store.lift(by=by)
    elif target:
        try:
            lifted = await store.lift(by=by, block=UUID(target))
        except ValueError:
            lifted = await store.lift(by=by, subject=target.split(":", 1)[-1])
    else:
        out.write("name a block (its id, a login or an address) or --all\n")
        return 2
    if audit is not None:
        await audit("security.block_lifted", {"by": by, "target": target or "all", "lifted": lifted})
    out.write(f"{lifted} block(s) lifted\n")
    return 0 if lifted else 1
