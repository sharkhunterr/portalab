"""016 T020/T021/T038 — role matrix (requester / other user / support / moderator / admin): own tickets
only, internal notes and staff-only fields hidden from requesters, staff actions refused to users, IDOR on
ticket and attachment ids denied, reassignment audited; attachments: magic-byte allowlist (a disguised
executable is refused), size/count limits, images re-encoded without EXIF, non-images download-only with
``nosniff``, sanitized names, the scanner hook, private attachments staff-only; the shared ``core.uploads``
helper is the one in use."""

import io
from uuid import UUID

import httpx
import pytest
from PIL import Image
from sqlalchemy import text

from portalab.capabilities.support import SCANNER, ScanVerdict
from tests.integration.identity.helpers import login
from tests.integration.support.conftest import SupportHarness

pytestmark = pytest.mark.integration


async def new_ticket(client: httpx.AsyncClient, name: str) -> dict:
    await login(client, name)
    body = {
        "type_key": "access_request",
        "title": "Need access",
        "fields": {
            "resource": "Books",
            "justification": "reading",
            "staff_notes": "should not be set by users",
        },
    }
    response = await client.post("/api/v1/tickets", json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def test_role_matrix(
    client: httpx.AsyncClient, support: SupportHarness, people: dict[str, UUID]
) -> None:
    ticket = await new_ticket(client, "ursula")
    tid = ticket["id"]
    assert "staff_notes" not in ticket["fields"] and all(
        d["key"] != "staff_notes" for d in ticket["field_defs"]
    )
    await login(client, "ulrich")  # another user: nothing, not even existence
    for method, path, body in (
        ("GET", f"/api/v1/tickets/{tid}", None),
        ("POST", f"/api/v1/tickets/{tid}/comments", {"body": "hi"}),
        ("POST", f"/api/v1/tickets/{tid}/transition", {"transition": "cancel"}),
    ):
        assert (await client.request(method, path, json=body)).status_code == 404, path
    for method, path, body in (
        ("GET", "/api/v1/support/tickets", None),
        ("POST", f"/api/v1/tickets/{tid}/assign", {"assignee_id": str(people["ulrich"])}),
        ("POST", f"/api/v1/tickets/{tid}/internal-notes", {"body": "x"}),
        ("POST", f"/api/v1/tickets/{tid}/tags", {"add": ["x"]}),
        ("PUT", "/api/v1/admin/support/types/x", {"label": "X"}),
    ):
        assert (await client.request(method, path, json=body)).status_code == 403, path
    await login(client, "mona")  # moderator: feedback, not tickets
    assert (await client.get(f"/api/v1/tickets/{tid}")).status_code == 404
    await login(client, "sam")
    staff_view = (await client.get(f"/api/v1/tickets/{tid}")).json()
    assert staff_view["fields"]["staff_notes"] == "should not be set by users" and staff_view["staff"] is True
    await client.post(f"/api/v1/tickets/{tid}/assign", json={"assignee_id": str(people["sam"])})
    await login(client, "boss")
    await client.post(
        f"/api/v1/tickets/{tid}/assign", json={"assignee_id": str(people["boss"])}
    )  # takes it from sam
    async with support.full.database.session() as session:
        audited = (
            (
                await session.execute(
                    text("SELECT action FROM audit.audit_entries WHERE action = 'ticket.reassigned'")
                )
            )
            .scalars()
            .all()
        )
    assert audited == ["ticket.reassigned"]
    queue = (await client.get("/api/v1/support/tickets", params={"q": "access"})).json()
    assert [t["id"] for t in queue["items"]] == [tid]


def _jpeg_with_exif() -> bytes:
    image = Image.new("RGB", (30, 30), (0, 0, 200))
    exif = Image.Exif()
    exif[0x010F] = "TellTaleCamera"
    out = io.BytesIO()
    image.save(out, format="JPEG", exif=exif)
    return out.getvalue()


async def upload(
    client: httpx.AsyncClient, tid: str, data: bytes, name: str, **params: object
) -> httpx.Response:
    return await client.post(
        f"/api/v1/tickets/{tid}/attachments",
        params={"filename": name, **params},
        content=data,
        headers={"Content-Type": "application/octet-stream"},
    )


async def test_attachments(
    client: httpx.AsyncClient, support: SupportHarness, people: dict[str, UUID]
) -> None:
    ticket = await new_ticket(client, "ursula")
    tid = ticket["id"]
    disguised = await upload(client, tid, b"MZ\x90\x00\x03" + b"\x00" * 200, "holiday.png")
    assert disguised.status_code == 422 and disguised.json()["code"] == "attachment.rejected"
    assert disguised.json()["reason"] == "type"
    photo = await upload(client, tid, _jpeg_with_exif(), "../../etc/photo.jpeg")
    assert photo.status_code == 201 and photo.json()["filename"] == "photo.jpg"
    log = await upload(client, tid, b"error: boom\n", "trace.txt")
    assert log.status_code == 201
    served = await client.get(f"/api/v1/tickets/attachments/{photo.json()['id']}")
    assert (
        served.headers["content-disposition"].startswith("inline") and b"TellTaleCamera" not in served.content
    )
    text_file = await client.get(f"/api/v1/tickets/attachments/{log.json()['id']}")
    assert (
        text_file.headers["content-disposition"].startswith("attachment")
        and text_file.headers["x-content-type-options"] == "nosniff"
    )
    assert (
        await upload(client, tid, b"x", "x.txt", private="true")
    ).status_code == 403  # private: staff only
    support.module.config = __import__("dataclasses").replace(
        support.module.config, attachments_max_per_post=2, attachments_max_bytes=50
    )
    too_many = await upload(client, tid, b"third\n", "c.txt")
    assert too_many.status_code == 422 and too_many.json()["reason"] == "too_many"
    support.module.config = __import__("dataclasses").replace(
        support.module.config, attachments_max_per_post=10
    )
    too_big = await upload(client, tid, b"x" * 60, "big.txt")
    assert too_big.status_code == 422 and too_big.json()["reason"] == "too_large"

    class Scanner:
        async def scan(self, data: bytes, content_type: str) -> ScanVerdict:
            return ScanVerdict(clean=b"EICAR" not in data, reason="signature")

    support.full.identity.capabilities.provide(SCANNER, Scanner(), instance_ref="scan", owner="test")
    infected = await upload(client, tid, b"EICAR test\n", "virus.txt")
    assert infected.status_code == 422 and infected.json()["reason"] == "scanner"
    await login(client, "sam")
    private = await upload(client, tid, b"staff only\n", "notes.txt", private="true")
    assert private.status_code == 201
    await login(client, "ursula")
    assert (await client.get(f"/api/v1/tickets/attachments/{private.json()['id']}")).status_code == 404
    await login(client, "ulrich")
    assert (await client.get(f"/api/v1/tickets/attachments/{photo.json()['id']}")).status_code == 404  # IDOR


def test_shared_upload_helper_is_used() -> None:
    import inspect

    from portalab.modules.support.attachments import service

    source = inspect.getsource(service)
    assert "from portalab.core.uploads import" in source and "PIL" not in source
