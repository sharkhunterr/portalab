"""Media metrics (T034): sync/poll health, unresolved/unlinked counts, candidate queue, merges, request
failures, section latency — ids and counts only, never titles, user names or source payloads."""

import re
import threading
from collections import Counter

from portalab.core.logging import get_logger

log = get_logger("portalab.media")

_METRIC = re.compile(r"^media\.[a-z_][a-z0-9_]*(\.[a-z0-9_]+)*$")


def metric_part(value: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", value.lower())


class MediaMetrics:
    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()
        self._gauges: dict[str, float] = {}
        self._lock = threading.Lock()

    def increment(self, name: str, amount: int = 1) -> None:
        if not _METRIC.fullmatch(name):
            raise ValueError(f"metric names are fixed identifiers, got {name!r}")
        with self._lock:
            self._counts[name] += amount

    def gauge(self, name: str, value: float) -> None:
        if not _METRIC.fullmatch(name):
            raise ValueError(f"metric names are fixed identifiers, got {name!r}")
        with self._lock:
            self._gauges[name] = value

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            return {**self._counts, **self._gauges}


metrics = MediaMetrics()
