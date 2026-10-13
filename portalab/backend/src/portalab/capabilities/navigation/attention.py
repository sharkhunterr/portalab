"""``shell.attention`` (#98): what waits for someone, as a small badge and a number on the navigation — a
purchase to validate (a film in 4K, a service's access), a proposal to moderate, a request to handle…

Each module provides how many items wait **for this principal** (only what they may act on), keyed by the
navigation entry that leads to them; the shell adds them up (an entry, its hub, its section) and serves
them at ``GET /api/v1/me/attention``. A provider that fails or is slow counts nothing."""

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from portalab.capabilities.registry import CapabilitySpec
from portalab.core.authz_port import Principal

ATTENTION = "shell.attention"


@runtime_checkable
class AttentionProvider(Protocol):
    async def counts(self, principal: Principal) -> Mapping[str, int]:
        """Navigation entry key → how many items wait there for this principal (0: nothing)."""
        ...


SPEC = CapabilitySpec(
    name=ATTENTION,
    version="1.0",
    protocol=AttentionProvider,
    multi_provider=True,
    description="What waits for a principal, per navigation entry (badges) (#98)",
)
