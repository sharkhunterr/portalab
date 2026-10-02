"""002 T050 — logs, metrics, audit records and events never contain passwords, tokens or raw identifiers."""

import io
import json
import logging

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from portalab.core.logging import JsonFormatter
from portalab.modules.identity.api.middleware import SESSION_COOKIE
from portalab.modules.identity.observability import metrics
from tests.integration.identity.helpers import PASSWORD, create_user, login, module_of

pytestmark = pytest.mark.integration


@pytest.fixture
def captured_logs() -> io.StringIO:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    previous_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    yield stream
    root.removeHandler(handler)
    root.setLevel(previous_level)


async def test_secrets_never_reach_logs_audit_or_events(
    app: FastAPI, client: httpx.AsyncClient, captured_logs: io.StringIO
) -> None:
    module = module_of(app)
    metrics.reset()
    await create_user(module, "secretive")
    await client.post("/api/v1/auth/login", json={"login": "secretive", "password": "wrong-password-xyz"})
    await client.post("/api/v1/auth/login", json={"login": "no-such-person", "password": "another-wrong-one"})
    response = await login(client, "secretive")
    token = client.cookies.get(SESSION_COOKIE)
    csrf = response.json()["csrf_token"]
    await client.get("/api/v1/me")
    await client.post("/api/v1/auth/logout")

    logs = captured_logs.getvalue()
    audit = json.dumps([record.context for record in module.ctx.audit.records], default=str)  # type: ignore[attr-defined]
    async with module.ctx.database.session() as session:
        events = (
            await session.execute(text("SELECT coalesce(json_agg(e)::text, '') FROM core.event_outbox e"))
        ).scalar()
    for haystack in (logs, audit, events or ""):
        for secret in (PASSWORD, "wrong-password-xyz", "another-wrong-one", token or "", csrf):
            assert secret not in haystack
        assert "no-such-person" not in haystack  # failed identifiers are hashed
    assert "identity.login.failed" in metrics.snapshot()
    assert metrics.snapshot()["identity.login.failed"] == 2
    assert all(name.startswith("identity.") for name in metrics.snapshot())


def test_metric_names_cannot_carry_identifiers() -> None:
    with pytest.raises(ValueError):
        metrics.increment("identity.login.failed.alice@example.org")
