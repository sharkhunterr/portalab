"""008 T023 — domain coverage checklist (FR-012): every listed domain kind must eventually register a
provider through the SDK. Kinds whose owning spec has not landed yet are reported as pending (xfail with
the owning spec), so the checklist turns green domain by domain."""

import pytest

from portalab.capabilities.search import SearchRegistry
from tests.integration.search.conftest import SearchHarness

pytestmark = pytest.mark.integration

EXPECTED = {
    "navigation": None,
    "services": None,
    "users": None,
    "media": None,
    "wiki": "011",
    "news": "009",
    "tickets": "016",
    "community": "012",
    "calendar": "014",
    "marketplace": "015",
    "statistics": "017",
    "gamification": "013",
}


@pytest.mark.parametrize("kind", sorted(EXPECTED))
async def test_domain_registers_a_provider(kind: str, search: SearchHarness) -> None:
    registry: SearchRegistry = search.registry
    if registry.provider(kind) is None:
        owner = EXPECTED[kind]
        if owner is None:
            pytest.fail(f"{kind!r} must be provided already")
        pytest.xfail(f"pending: provider delivered by spec {owner}")
    assert registry.provider(kind) is not None
