"""Issue 122 — what a server report says as service signals: a parity check running (or paused), its
progress by tens, the containers with an update or stopped, the warnings; unknown is ``None``."""

from portalab.modules.health.infra.signals import SIGNALS

PICK = {key: pick for key, _kind, pick, _label, _description in SIGNALS}


def test_parity() -> None:
    running = {"array_state": "STARTED", "parity": {"status": "running", "running": True, "progress": 47.3}}
    paused = {"array_state": "STARTED", "parity": {"status": "paused", "running": False, "progress": 12}}
    idle = {"array_state": "STARTED", "parity": None}
    assert PICK["infrastructure.parity_running"](running) is True
    assert PICK["infrastructure.parity_running"](paused) is True
    assert PICK["infrastructure.parity_running"](idle) is False
    assert PICK["infrastructure.parity_running"]({}) is None  # no array: not a server with parity
    assert PICK["infrastructure.parity_progress"](running) == 40
    assert PICK["infrastructure.parity_progress"](idle) is None


def test_containers_and_warnings() -> None:
    report = {
        "containers": [
            {"name": "plex", "state": "running", "update_available": True},
            {"name": "sonarr", "state": "exited", "update_available": False},
            {"name": "radarr", "state": "running", "update_available": True},
        ],
        "warnings": ["storage_low", "disk_errors"],
    }
    assert PICK["infrastructure.updates_available"](report) == 2
    assert PICK["infrastructure.containers_stopped"](report) == 1
    assert PICK["infrastructure.warnings"](report) == "disk_errors, storage_low"
    assert PICK["infrastructure.warnings"]({}) == "none"
    assert PICK["infrastructure.updates_available"]({}) is None
