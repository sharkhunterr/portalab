"""Intrusion guard (spec 028 FR-039…FR-041, from the POC of issue 1): a member — or anyone — probing what they
may not reach is blocked.

Every API answer is weighed: a refusal (403) counts, a refusal on the administration counts double, an unknown
address of the administration (404) counts — someone listing what it has — and an address shaped like an
attack (a path leaving its folder, an encoded slash or null byte, markup or a system path in it) counts
heavily whatever the answer. Points are kept per session and per address, in this process's memory, for a
window; past the limit, that session — and the member's account: signing in again changes nothing — is blocked
for a while, every session of theirs signed out; much further, the address is blocked for requests without a
session (signing in from it, anonymous probing), never for the members already signed in from it.

Blocks are kept in the database (``identity.security_blocks``): every process loads them every few seconds, a
restart keeps them, the holders of ``security.manage`` lift them (``/api/v1/admin/security/blocks``) — and so
does anyone at the server's console (``portalab security blocks lift``), the Admin's own block included.
"""

import re
import time
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

WINDOW_SECONDS = 600
SESSION_LIMIT = 20
ADDRESS_LIMIT = 60
BLOCK_SECONDS = 900
# a path leaving its folder, an encoded dot, slash or null byte, markup, a system file: an attack's shape
ATTACK = re.compile(
    r"\.\./|/\.\.|%2e%2e|%2e/|/%2e|%00|\\x00|%2f\.\.|\.\.%2f|%5c|<script|%3cscript|/etc/passwd|/proc/self",
    re.I,
)
KINDS = {"session": "session", "ip": "address"}  # the guard's key prefix → the stored kind


def weigh(path: str, query: str, status: int) -> tuple[int, str] | None:
    """How suspicious an API answer is (points, why) — ``None``: not at all."""
    if ATTACK.search(path) or ATTACK.search(query):
        return 8, "attack-shaped address"
    if status == 403:
        return (2, "refused on the administration") if "/admin/" in path else (1, "refused")
    if status in (401, 404) and "/admin/" in path:
        return 1, "unknown administration address"  # someone listing what the administration has
    return None


@dataclass
class Block:
    key: str
    until: float
    reason: str
    points: int
    paths: list[str] = field(default_factory=list)
    id: str | None = None  # its row, once stored


class IntrusionGuard:
    def __init__(
        self,
        *,
        window: float = WINDOW_SECONDS,
        session_limit: int = SESSION_LIMIT,
        address_limit: int = ADDRESS_LIMIT,
        block_seconds: float = BLOCK_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.window = window
        self.limits = {"session": session_limit, "ip": address_limit}
        self.block_seconds = block_seconds
        self.clock = clock
        self._points: dict[str, deque[tuple[float, int, str]]] = {}
        self._blocks: dict[str, Block] = {}
        self._users: dict[str, tuple[float, str, str | None]] = {}  # an account: until, who (login), row
        self._stored: set[str] = set()  # the keys the database held at the last load
        self.enabled = True  # a test probing every route on purpose switches it off

    def configure(
        self,
        *,
        window: float | None = None,
        session_limit: int | None = None,
        address_limit: int | None = None,
        block_seconds: float | None = None,
    ) -> None:
        """The administrator's thresholds (FR-041)."""
        if window:
            self.window = window
        if session_limit:
            self.limits["session"] = session_limit
        if address_limit:
            self.limits["ip"] = address_limit
        if block_seconds:
            self.block_seconds = block_seconds

    def block_user(self, user_id: str, who: str, row: str | None = None) -> None:
        """The account behind a blocked session: every session of theirs refused (signing in again changes
        nothing) for as long as the block lasts."""
        self._users[user_id] = (self.clock() + self.block_seconds, who, row)

    def user_blocked(self, user_id: str) -> float | None:
        entry = self._users.get(user_id)
        if entry is None:
            return None
        left = entry[0] - self.clock()
        if left <= 0:
            del self._users[user_id]
            return None
        return left

    def any_user_blocked(self) -> bool:
        return bool(self._users)

    def blocked(self, keys: list[str]) -> float | None:
        """Seconds left on the first of these keys still blocked (``None``: none is)."""
        now = self.clock()
        for key in keys:
            block = self._blocks.get(key)
            if block is None:
                continue
            if block.until <= now:
                del self._blocks[key]
                continue
            return block.until - now
        return None

    def strike(self, keys: list[str], points: int, reason: str, path: str) -> list[Block]:
        """Counts a suspicious answer against each key; returns the blocks it starts."""
        if not self.enabled:
            return []
        now = self.clock()
        started: list[Block] = []
        for key in keys:
            kind = key.split(":", 1)[0]
            limit = self.limits.get(kind)
            if limit is None or key in self._blocks:
                continue
            history = self._points.setdefault(key, deque())
            history.append((now, points, path[:200]))
            while history and history[0][0] < now - self.window:
                history.popleft()
            total = sum(p for _, p, _ in history)
            if total >= limit:
                block = Block(
                    key, now + self.block_seconds, reason, total, [p for _, _, p in list(history)[-8:]]
                )
                self._blocks[key] = block
                self._points.pop(key, None)
                started.append(block)
        return started

    def load(self, rows: Iterable[Any], *, wall: datetime | None = None) -> None:
        """The blocks the database holds (``store.ActiveBlock``), made this process's: a block stored by
        another process is enforced here too, a block lifted (or ended) there is lifted here. A block started
        here but not stored yet is kept."""
        now, wall = self.clock(), wall or datetime.now(UTC)
        blocks: dict[str, Block] = {}
        users: dict[str, tuple[float, str, str | None]] = {}
        for row in rows:
            until = now + max(0.0, (row.until - wall).total_seconds())
            if row.kind == "account":
                users[row.subject] = (until, row.label or row.subject, str(row.id))
                continue
            key = f"{'session' if row.kind == 'session' else 'ip'}:{row.subject}"
            blocks[key] = Block(key, until, row.reason, row.points, list(row.paths), str(row.id))
        stored = set(blocks) | {f"user:{u}" for u in users}
        for key, block in self._blocks.items():
            if key not in blocks and key not in self._stored and block.id is None and block.until > now:
                blocks[key] = block  # just started here: its row is on its way
        for user, entry in self._users.items():
            if (
                user not in users
                and f"user:{user}" not in self._stored
                and entry[2] is None
                and entry[0] > now
            ):
                users[user] = entry
        self._blocks, self._users, self._stored = blocks, users, stored

    def blocks(self) -> list[dict[str, Any]]:
        now = self.clock()
        accounts = [
            {"id": row, "key": f"user:{user}", "kind": "user", "who": who, "seconds_left": round(until - now)}
            for user, (until, who, row) in self._users.items()
            if until > now
        ]
        return accounts + [
            {
                "id": b.id,
                "key": b.key,
                "kind": b.key.split(":", 1)[0],
                "seconds_left": round(b.until - now),
                "reason": b.reason,
                "points": b.points,
                "paths": b.paths,
            }
            for b in self._blocks.values()
            if b.until > now
        ]

    def lift(self, key: str | None = None) -> int:
        if key is None:
            count = len(self._blocks) + len(self._users)
            self._blocks.clear()
            self._users.clear()
            return count
        if key.startswith("user:"):
            return 1 if self._users.pop(key[5:], None) else 0
        return 1 if self._blocks.pop(key, None) else 0


def stored_kind(key: str) -> tuple[str, str]:
    """A guard key (``session:<hash>``, ``ip:<address>``) as a stored block's kind and subject."""
    prefix, _, subject = key.partition(":")
    return KINDS.get(prefix, prefix), subject
