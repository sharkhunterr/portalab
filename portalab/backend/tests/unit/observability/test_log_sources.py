"""Issue 158 — where a log line comes from, as the administrators think of it."""

import pytest

from portalab.modules.observability.logs.service import message_of, source_of


@pytest.mark.parametrize(
    ("logger", "fields", "source"),
    [
        ("portalab.modules.media.sync", {}, "media"),
        ("portalab.connectors.plex.client", {}, "connector:plex"),
        ("portalab.core.jobs.worker", {}, "jobs"),
        ("portalab.core.db", {}, "core"),
        ("portalab.app.worker", {}, "app"),
        ("portalab.app", {}, "app"),
        ("portalab.app", {"method": "GET", "path": "/x", "status": 200}, "http"),
        ("portalab.cli", {}, "cli"),
        ("portalab.modules.plugins.runtime", {"plugin": "weather"}, "plugin:weather"),
        ("uvicorn.error", {}, "server"),
        ("sqlalchemy.pool", {}, "database"),
        ("httpx", {}, "http.out"),
        ("watchfiles.main", {}, "watchfiles"),
    ],
)
def test_source_of(logger: str, fields: dict[str, object], source: str) -> None:
    assert source_of(logger, fields) == source


def test_a_request_line_says_what_it_was() -> None:
    fields = {"method": "GET", "path": "/api/v1/me", "status": 200, "duration_ms": 12.5}
    assert message_of("request", fields) == "GET /api/v1/me → 200 · 12.5 ms"
    assert message_of("request", {}) == "request"
    assert message_of("synchronised", fields) == "synchronised"
