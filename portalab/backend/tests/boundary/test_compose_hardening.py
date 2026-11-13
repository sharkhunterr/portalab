"""Issue 399 — the shipped Compose file stays hardened: every service's image files read-only, no privilege
gained, every capability dropped (only the few the init and the database's entrypoint need given back), never
privileged nor on the host's network, secrets mounted read-only, and only the portal itself published."""

from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.boundary

COMPOSE = Path(__file__).resolve().parents[3] / "deploy" / "docker-compose.yml"
ALLOWED_CAPS = {
    "init": {"CHOWN", "DAC_OVERRIDE", "FOWNER"},  # writes the secrets, owned by each service's user
    "postgres": {"CHOWN", "DAC_OVERRIDE", "FOWNER", "SETGID", "SETUID"},  # hands its folder over, drops to it
}


def services() -> dict[str, dict[str, Any]]:
    return dict(yaml.safe_load(COMPOSE.read_text())["services"])


@pytest.mark.parametrize("name", list(services()))
def test_every_service_is_hardened(name: str) -> None:
    service = services()[name]
    assert service.get("read_only") is True, name
    assert "no-new-privileges:true" in service.get("security_opt", []), name
    assert service.get("cap_drop") == ["ALL"], name
    assert set(service.get("cap_add", [])) <= ALLOWED_CAPS.get(name, set()), name
    assert not service.get("privileged"), name
    assert service.get("network_mode") in (None, "none"), name
    assert service.get("pid") is None and service.get("ipc") is None, name
    for volume in service.get("volumes", []):
        assert "docker.sock" not in volume, name
        if volume.split(":")[1].startswith("/run/secrets"):
            assert volume.endswith(":ro"), volume


def test_only_the_portal_is_published() -> None:
    assert {name for name, service in services().items() if service.get("ports")} == {"portalab"}
