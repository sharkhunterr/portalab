"""Administration metrics (T031): configuration changes, invalid stored values, policy overrides, toggles,
panel latency/failures. Setting keys and panel ids only — never values or user identifiers."""

import re
import threading
from collections import Counter

from portalab.core.logging import get_logger

log = get_logger("portalab.administration")

_METRIC = re.compile(r"^admin\.[a-z_]+(\.[a-z0-9_]+)*$")


class AdminMetrics:
    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()
        self._timings: dict[str, float] = {}
        self._lock = threading.Lock()

    def increment(self, name: str, amount: int = 1) -> None:
        if not _METRIC.fullmatch(name):
            raise ValueError(f"metric names are fixed identifiers, got {name!r}")
        with self._lock:
            self._counts[name] += amount

    def timing(self, name: str, milliseconds: float) -> None:
        if not _METRIC.fullmatch(name):
            raise ValueError(f"metric names are fixed identifiers, got {name!r}")
        with self._lock:
            self._timings[name] = milliseconds

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            return {**self._counts, **self._timings}

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()
            self._timings.clear()


metrics = AdminMetrics()
