"""Campaign metrics (T030): active campaigns, late boundaries, matched vs unknown conditions, attribute
provider failures, overrides — counts only."""

import re
import threading
from collections import Counter

from portalab.core.logging import get_logger

log = get_logger("portalab.campaigns")
_METRIC = re.compile(r"^campaigns\.[a-z_][a-z0-9_]*(\.[a-z0-9_]+)*$")


class CampaignMetrics:
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


metrics = CampaignMetrics()
