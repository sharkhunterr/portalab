"""Identity metrics and structured logs (plan §10, T050).

Counters only carry *kinds* of outcomes (logins ok/failed/throttled, transitions by type, saga step failures,
session revocations) — never identifiers, logins, tokens or addresses. Observability (spec 025) scrapes
:meth:`IdentityMetrics.snapshot` through the kernel metrics hooks once they exist.
"""

import re
import threading
from collections import Counter

from portalab.core.logging import get_logger

log = get_logger("portalab.identity")

_METRIC = re.compile(r"^identity\.[a-z_]+(\.[a-z_]+)*$")


class IdentityMetrics:
    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()
        self._lock = threading.Lock()

    def increment(self, name: str, amount: int = 1) -> None:
        if not _METRIC.fullmatch(name):
            raise ValueError(f"metric names are fixed identifiers, got {name!r}")
        with self._lock:
            self._counts[name] += amount

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counts)

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()


metrics = IdentityMetrics()


def log_event(message: str, **fields: str | int | None) -> None:
    """Structured identity log line; callers pass outcome kinds and opaque ids only."""
    log.info(message, extra={"fields": fields})
