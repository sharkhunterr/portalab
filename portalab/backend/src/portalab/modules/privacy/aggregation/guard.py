"""Aggregation guard (T031; FR-023/024, R8): no aggregate cell may describe fewer than
``privacy.minAggregateSize`` people. Small cells are suppressed; when exactly one cell would be suppressed
while a total is published, the next smallest cell is suppressed too, so the hidden value cannot be
recomputed by subtraction (complementary suppression)."""

from collections.abc import Mapping

SUPPRESSED = None


class AggregationGuard:
    def __init__(self, min_size: int = 5) -> None:
        if min_size < 1:
            raise ValueError("min_size must be >= 1")
        self.min_size = min_size

    def guard(self, groups: Mapping[str, int], *, with_total: bool = False) -> dict[str, int | None]:
        result: dict[str, int | None] = {}
        suppressed: list[str] = []
        for key, count in groups.items():
            if 0 < count < self.min_size:
                result[key] = SUPPRESSED
                suppressed.append(key)
            else:
                result[key] = count
        if with_total and len(suppressed) == 1:
            visible = sorted((count, key) for key, count in result.items() if count)
            if visible:
                result[visible[0][1]] = SUPPRESSED
        return result
