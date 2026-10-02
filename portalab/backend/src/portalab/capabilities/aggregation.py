"""``privacy.aggregation_guard`` capability (spec 021 R8; consumed by Statistics 017)."""

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from portalab.capabilities.registry import CapabilitySpec

CAPABILITY = "privacy.aggregation_guard"


@runtime_checkable
class AggregationGuardPort(Protocol):
    def guard(self, groups: Mapping[str, int], *, with_total: bool = False) -> dict[str, int | None]: ...


SPEC = CapabilitySpec(
    name=CAPABILITY,
    version="1.0",
    protocol=AggregationGuardPort,
    multi_provider=False,
    description="Suppresses aggregate cells below the minimum group size.",
)
