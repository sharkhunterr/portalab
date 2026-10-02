"""021 T030 — small cells are suppressed; threshold configurable; no reconstruction via the total."""

import pytest

from portalab.capabilities.aggregation import AggregationGuardPort
from portalab.modules.privacy.aggregation.guard import AggregationGuard

pytestmark = pytest.mark.unit


def test_small_cells_suppressed() -> None:
    guard = AggregationGuard(5)
    assert guard.guard({"a": 12, "b": 3, "c": 0}) == {"a": 12, "b": None, "c": 0}
    assert AggregationGuard(2).guard({"b": 3}) == {"b": 3}
    assert isinstance(guard, AggregationGuardPort)


def test_complementary_suppression_with_total() -> None:
    result = AggregationGuard(5).guard({"a": 20, "b": 9, "c": 2}, with_total=True)
    assert result == {"a": 20, "b": None, "c": None}  # c alone hidden would be total - a - b


def test_invalid_threshold() -> None:
    with pytest.raises(ValueError):
        AggregationGuard(0)
