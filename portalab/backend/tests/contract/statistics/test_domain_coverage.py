"""017 T023 — domain coverage checklist (FR-009): every listed domain ships a definition pack (the owning
spec in comment); #84 delivered the last ones — activity, community, requests and trends."""

import pytest

from portalab.capabilities.statistics import PackRegistry
from portalab.modules.statistics.packs.registry import register_builtin

EXPECTED = {
    "users": "002",
    "services": "006",
    "activity": "007",
    "media": "024",
    "playback": "024",
    "reading": "024",
    "gaming": "024",
    "community": "012",
    "gamification": "013",
    "requests": "016",
    "trends": "017",
}


@pytest.mark.parametrize("domain", sorted(EXPECTED))
def test_domain_ships_a_pack(domain: str) -> None:
    packs = PackRegistry()
    register_builtin(packs)
    domains = {d for _, d, _, _ in packs.packs()}
    assert domain in domains, f"{domain!r} ships no statistics pack (spec {EXPECTED[domain]})"
