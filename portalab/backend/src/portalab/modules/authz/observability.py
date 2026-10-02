"""Authorization metrics (plan §10, T033): decisions by outcome, sensitive denials, audit-write failures,
confirmations. Only permission keys and outcome kinds — never user ids, tokens or resource ids."""

import re
import threading
from collections import Counter
from contextlib import suppress

from portalab.core.logging import get_logger

log = get_logger("portalab.authz")

_METRIC = re.compile(r"^authz\.[a-z_][a-z0-9_]*(\.[a-z0-9_]+)*$")


class AuthzMetrics:
    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()
        self._lock = threading.Lock()

    def increment(self, name: str, amount: int = 1) -> None:
        if not _METRIC.fullmatch(name):
            raise ValueError(f"metric names are fixed identifiers, got {name!r}")
        with self._lock:
            self._counts[name] += amount

    def decision(self, permission: str, allowed: bool) -> None:
        """Count a decision; metrics never interfere with authorization (fail-open)."""
        outcome = "allow" if allowed else "deny"
        part = re.sub(r"[^a-z0-9_.]", "_", permission.lower())
        with suppress(ValueError):
            self.increment(f"authz.decisions.{outcome}")
            self.increment(f"authz.decisions.{outcome}.{part}")

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counts)

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()


metrics = AuthzMetrics()
