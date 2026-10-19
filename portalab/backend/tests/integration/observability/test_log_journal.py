"""Issue 158 — the log journal: each process's lines (already redacted) stored, read newest first by the
administrators, filtered, followed live and exported; never a secret; every reading audited."""

import logging

import httpx
from fastapi import FastAPI
from sqlalchemy import text

from portalab.core.logging import LogTap, register_secret_value
from tests.connectors_fixtures import admin_client
from tests.observability_fixtures import ObsHarness


def _emit(tap: LogTap, name: str, level: int, message: str, **fields: object) -> None:
    record = logging.getLogger(name).makeRecord(name, level, __file__, 1, message, (), None)
    record.fields = fields
    tap.handle(record)


async def test_the_journal_stores_reads_and_exports_redacted_lines(
    app: FastAPI, client: httpx.AsyncClient, ob: ObsHarness
) -> None:
    tap = LogTap(capacity=100)
    ob.module.logs.tap = tap
    register_secret_value("very-secret-value-158")
    _emit(tap, "portalab.modules.media.sync", logging.INFO, "synchronised 12 items")
    _emit(tap, "portalab.connectors.plex.client", logging.ERROR, "plex answered 500", attempt=2)
    _emit(tap, "portalab.core.jobs.worker", logging.WARNING, "job late password=hunter22 here")
    _emit(tap, "uvicorn.error", logging.INFO, "token very-secret-value-158 seen", api_key="abc")
    _emit(tap, "portalab.modules.observability.logs.service", logging.WARNING, "the journal itself")
    assert await ob.module.logs.store("serve") == 4  # the journal never journals itself
    request = {"method": "GET", "path": "/api/v1/me", "status": 200, "duration_ms": 3.0}
    _emit(tap, "portalab.app", logging.INFO, "request", **request)
    await ob.module.logs.store("serve")

    await admin_client(app, client, ob.hl.cn)
    every = (await client.get("/api/v1/admin/observability/logs")).json()
    assert every["items"][0]["source"] == "http" and every["items"][0]["message"].startswith("GET /api/v1/me")
    page = (await client.get("/api/v1/admin/observability/logs", params={"exclude": "http"})).json()
    assert [line["source"] for line in page["items"]] == ["server", "jobs", "connector:plex", "media"]
    assert page["sources"] == ["connector:plex", "http", "jobs", "media", "server"]
    dump = str(page)
    assert "hunter22" not in dump and "very-secret-value-158" not in dump
    assert page["items"][0]["fields"] == {"api_key": "***"}
    assert page["items"][2]["fields"] == {"attempt": 2} and page["items"][0]["process"] == "serve"

    errors = (await client.get("/api/v1/admin/observability/logs", params={"level": "ERROR"})).json()
    assert [line["message"] for line in errors["items"]] == ["plex answered 500"]
    found = (await client.get("/api/v1/admin/observability/logs", params={"q": "12 ITEMS"})).json()
    assert [line["source"] for line in found["items"]] == ["media"]
    picked = await client.get(
        "/api/v1/admin/observability/logs", params=[("source", "media"), ("source", "jobs")]
    )
    assert {line["source"] for line in picked.json()["items"]} == {"media", "jobs"}

    newest = page["items"][0]["seq"]
    _emit(tap, "portalab.modules.media.sync", logging.INFO, "one more")
    await ob.module.logs.store("worker")
    live = (
        await client.get("/api/v1/admin/observability/logs", params={"after": newest, "exclude": "http"})
    ).json()
    assert [(line["message"], line["process"]) for line in live["items"]] == [("one more", "worker")]
    assert live["sources"] is None
    older = (
        await client.get("/api/v1/admin/observability/logs", params={"before": newest, "exclude": "http"})
    ).json()
    assert len(older["items"]) == 3

    as_text = await client.get("/api/v1/admin/observability/logs/export", params={"level": "ERROR"})
    assert as_text.status_code == 200 and "attachment" in as_text.headers["content-disposition"]
    assert "[connector:plex] plex answered 500" in as_text.text and '"attempt": 2' in as_text.text
    as_json = await client.get("/api/v1/admin/observability/logs/export", params={"format": "json"})
    assert [line["message"] for line in as_json.json()][-1] == "one more"  # oldest first, as a log reads

    async with ob.database.session() as session:
        actions = list(
            (
                await session.execute(
                    text(
                        "SELECT action FROM audit.audit_entries WHERE action LIKE 'observability.logs_%' "
                        "ORDER BY occurred_at"
                    )
                )
            ).scalars()
        )
    # the reading once (the page follows the journal: not one entry per refresh), every export
    assert actions == [
        "observability.logs_viewed",
        "observability.logs_exported",
        "observability.logs_exported",
    ]


async def test_the_journal_is_bounded(ob: ObsHarness) -> None:
    tap = LogTap(capacity=3)
    ob.module.logs.tap = tap
    for n in range(5):
        _emit(tap, "portalab.modules.media.sync", logging.INFO, f"line {n}")
    assert tap.dropped == 2  # a flood never slows the process: the oldest waiting lines go
    assert await ob.module.logs.store("serve") == 3
    assert await ob.module.logs.trim() == 0  # far under the maximum count
    assert await ob.count("log_entries") == 3
