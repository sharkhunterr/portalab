"""Community metrics (T015): feed projections, section failures by section, shelf loads — counts only."""

import re
import threading
from collections import Counter

from portalab.core.logging import get_logger

log = get_logger("portalab.community")
_METRIC = re.compile(r"^community\.[a-z_][a-z0-9_]*(\.[a-z0-9_]+)*$")


class CommunityMetrics:
    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()
        self._lock = threading.Lock()

    def increment(self, name: str, amount: int = 1) -> None:
        if not _METRIC.fullmatch(name):
            raise ValueError(f"metric names are fixed identifiers, got {name!r}")
        with self._lock:
            self._counts[name] += amount

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            return dict(self._counts)


metrics = CommunityMetrics()
