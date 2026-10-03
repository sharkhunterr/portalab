"""017 T023 — domain coverage checklist (FR-009): every listed domain eventually ships a definition pack.
Domains whose owning spec has not landed are reported pending (xfail with the owner)."""

import pytest

from portalab.capabilities.statistics import PackRegistry
from portalab.modules.statistics.packs.registry import register_builtin

EXPECTED = {
    "users": None,
    "services": None,
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
    if domain not in domains:
        owner = EXPECTED[domain]
        if owner is None:
            pytest.fail(f"{domain!r} must ship already")
        pytest.xfail(f"pending: pack delivered by spec {owner}")
