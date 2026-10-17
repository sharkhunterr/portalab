"""029 (FR-018 to FR-020): every operation of the API resolves to a label; nothing of the administration, the
account, security, privacy or the streams is ever exposed; every label names a route that exists (a typo
would silently forbid it). The routes are those of ``backend/openapi.json`` (kept in step by the API drift
check)."""

import json
from pathlib import Path

import pytest

from portalab.app.exposure_api import declare_all
from portalab.capabilities.exposure import (
    Exposure,
    ExposureError,
    ExposureRegistry,
    OperationLabel,
    committing,
    default_exposure,
    read,
)

OPENAPI = json.loads((Path(__file__).resolve().parents[2] / "openapi.json").read_text(encoding="utf-8"))
ROUTES = sorted(
    (method.upper(), path)
    for path, item in OPENAPI["paths"].items()
    for method in item
    if method in ("get", "post", "put", "patch", "delete")
)


def test_every_route_resolves_and_the_resolved_table_is_sane() -> None:
    table = {f"{m} {p}": default_exposure.resolve(m, p).exposure for m, p in ROUTES}
    exposed = {k: v for k, v in table.items() if v is not Exposure.FORBIDDEN}
    assert exposed, "nothing exposed at all"
    for key, exposure in exposed.items():
        method, path = key.split(" ", 1)
        assert (exposure is Exposure.READ) == (method == "GET"), key
        assert "/admin" not in path and "/auth" not in path, key


def test_every_label_names_a_route_that_exists() -> None:
    routes = {f"{m} {p}" for m, p in ROUTES}
    stale = sorted(set(default_exposure.declared()) - routes)
    assert stale == [], f"labels naming no route: {stale}"


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/admin/visuals",
        "/api/v1/auth/login",
        "/api/v1/me/seal",
        "/api/v1/me/deletion",
        "/api/v1/me/preferences",
        "/api/v1/privacy/requests",
        "/api/v1/media/{object_id}/player/start",
        "/api/v1/media/player/{ticket}/image",
        "/api/v1/visuals/active",
        "/api/v1/exposure",
    ],
)
def test_forbidden_prefixes_win_over_any_declaration(path: str) -> None:
    registry = declare_all(ExposureRegistry())
    registry.declare(read(path, "x", "x"))
    assert registry.resolve("GET", path).exposure is Exposure.FORBIDDEN


def test_an_unlabelled_route_is_forbidden() -> None:
    assert default_exposure.resolve(
        "POST", "/api/v1/community/proposals/{proposal_id}/withdraw"
    ).exposure is (Exposure.FORBIDDEN)


def test_labels_follow_the_rules() -> None:
    registry = ExposureRegistry()
    with pytest.raises(ExposureError):
        registry.declare(OperationLabel("POST", "/api/v1/x", Exposure.READ, {"en": "x"}))
    with pytest.raises(ExposureError):
        registry.declare(OperationLabel("GET", "/api/v1/x", Exposure.COMMITTING, {"en": "x"}))
    with pytest.raises(ExposureError):
        registry.declare(OperationLabel("POST", "/api/v1/x", Exposure.COMMITTING, {"en": "x"}))
    registry.declare(committing("POST", "/api/v1/x", "x", "x", confirm_en="Do x", confirm_fr="Faire x"))


def test_every_committing_operation_states_what_it_engages() -> None:
    for label in default_exposure.exposable():
        if label.exposure is Exposure.COMMITTING:
            assert label.confirm and label.confirm.get("en") and label.confirm.get("fr"), label.key
