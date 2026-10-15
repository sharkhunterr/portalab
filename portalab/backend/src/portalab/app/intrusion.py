"""Intrusion guard (issue 1, POC): a member — or anyone — probing what they may not reach is blocked.

Every API answer is weighed: a refusal (403) counts, a refusal on the administration counts double, an unknown
address of the administration (404) counts — someone listing what it has — and an
address shaped like an attack (a path leaving its folder, an encoded slash or null byte, markup or a system
path in it) counts heavily whatever the answer. Points are kept per session and per address for ten minutes;
past the limit, that session — and the member's account: signing in again changes nothing — is blocked for a
while, every session of theirs signed out; much further, the address is blocked for requests without a session
(signing in from it, anonymous probing), never for the members already signed in from it. The action goes to
the audit log and the holders of ``security.manage`` are alerted. The administrators see and lift the blocks
(``/api/v1/admin/security/blocks``). Kept in the process's memory (a restart lifts every block).
"""

import re
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Annotated, Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import Unavailable

WINDOW_SECONDS = 600
SESSION_LIMIT = 20
ADDRESS_LIMIT = 60
BLOCK_SECONDS = 900
# a path leaving its folder, an encoded dot, slash or null byte, markup, a system file: an attack's shape
ATTACK = re.compile(
    r"\.\./|/\.\.|%2e%2e|%2e/|/%2e|%00|\\x00|%2f\.\.|\.\.%2f|%5c|<script|%3cscript|/etc/passwd|/proc/self",
    re.I,
)

Alert = Callable[[dict[str, Any]], Awaitable[None]]


def weigh(path: str, query: str, status: int) -> tuple[int, str] | None:
    """How suspicious an API answer is (points, why) — ``None``: not at all."""
    if ATTACK.search(path) or ATTACK.search(query):
        return 8, "attack-shaped address"
    if status == 403:
        return (2, "refused on the administration") if "/admin/" in path else (1, "refused")
    if status == 404 and "/admin/" in path:
        return 1, "unknown administration address"  # someone listing what the administration has
    return None


@dataclass
class Block:
    key: str
    until: float
    reason: str
    points: int
    paths: list[str] = field(default_factory=list)


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
        self._users: dict[str, tuple[float, str]] = {}  # a member's account: until, who (their login)
        self.enabled = True  # a test probing every route on purpose switches it off

    def block_user(self, user_id: str, who: str) -> None:
        """The account behind a blocked session: every session of theirs refused (signing in again changes
        nothing) for as long as the block lasts."""
        self._users[user_id] = (self.clock() + self.block_seconds, who)

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

    def blocks(self) -> list[dict[str, Any]]:
        now = self.clock()
        accounts = [
            {"key": f"user:{user}", "kind": "user", "who": who, "seconds_left": round(until - now)}
            for user, (until, who) in self._users.items()
            if until > now
        ]
        return accounts + [
            {
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


router = APIRouter(prefix="/api/v1", tags=["security"])
Manager = Annotated[Principal, require("security.manage")]


def _guard(request: Request) -> IntrusionGuard:
    guard: IntrusionGuard | None = request.app.state._state.get("intrusion_guard")
    if guard is None:
        raise Unavailable("The intrusion guard is not running.", code="security.guard_unavailable")
    return guard


@router.get("/admin/security/blocks")
async def blocks(_: Manager, request: Request) -> dict[str, Any]:
    return {"blocks": _guard(request).blocks()}


class LiftIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str | None = Field(default=None, max_length=200)  # none: every block


@router.post("/admin/security/blocks/lift")
async def lift(_: Manager, request: Request, body: LiftIn) -> dict[str, Any]:
    return {"lifted": _guard(request).lift(body.key)}
