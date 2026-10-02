"""Privacy metrics (T035): visibility decisions by level/outcome, active overrides, retention rows by target,
checkpoint lag, verification status, rate-limit hits. Never identifiers or data values."""

import re
import threading
from collections import Counter

from portalab.core.logging import get_logger

log = get_logger("portalab.privacy")

_METRIC = re.compile(r"^(privacy|audit|security)\.[a-z_]+(\.[a-z0-9_]+)*$")


class PrivacyMetrics:
    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()
        self._gauges: dict[str, float] = {}
        self._lock = threading.Lock()

    def increment(self, name: str, amount: int = 1) -> None:
        self._check(name)
        with self._lock:
            self._counts[name] += amount

    def gauge(self, name: str, value: float) -> None:
        self._check(name)
        with self._lock:
            self._gauges[name] = value

    @staticmethod
    def _check(name: str) -> None:
        if not _METRIC.fullmatch(name):
            raise ValueError(f"metric names are fixed identifiers, got {name!r}")

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            return {**self._counts, **self._gauges}

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()
            self._gauges.clear()


metrics = PrivacyMetrics()
