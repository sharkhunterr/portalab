"""T054 — the OpenAPI schema equals the committed snapshot (breaking-change guard, api-conventions).

When an API change is intentional: run ``uv run portalab openapi -o openapi.json`` then ``npm run gen:api``
in ``frontend/`` and commit both files; reviewers then see the contract diff explicitly.
"""

import json

import pytest

from portalab.app.composition import BACKEND_DIR
from portalab.app.main import create_app

pytestmark = pytest.mark.contract

SNAPSHOT = BACKEND_DIR / "openapi.json"


def test_openapi_matches_committed_snapshot() -> None:
    current = create_app(migration_heads=set()).openapi()
    committed = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert current == committed, "API contract changed: regenerate openapi.json and the frontend client"


def test_every_operation_is_versioned_or_health() -> None:
    schema = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    for path in schema["paths"]:
        assert path.startswith("/api/v1/") or path in {"/healthz", "/readyz"}, path
