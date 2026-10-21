"""016 T019/T027/T029/T031/T036 — ticket lifecycle (create → assign → transition → resolve → close/reopen)
with an append-only history and events, optimistic concurrency (``If-Match`` ⇒ 409), precheck surfacing
open incidents and wiki suggestions without AI (sections degrade independently), one incident per ticket,
no merge endpoint, incident resolution never touches tickets, an audited bulk action; feedback forms that
never create tickets, review/dismiss, explicit conversions with provenance (once each, unavailable targets
disabled with a reason); retention/erasure tombstone the requester and purge attachments/private fields."""

from uuid import UUID

import httpx
import pytest
from sqlalchemy import text

from portalab.capabilities.content import KNOWLEDGE, KnowledgeHit
from portalab.capabilities.support import CONTRIBUTIONS
from tests.integration.identity.helpers import login
from tests.integration.support.conftest import SupportHarness

pytestmark = pytest.mark.integration


async def outbox(support: SupportHarness, prefix: str) -> list[str]:
    async with support.full.database.session() as session:
        rows = await session.execute(
            text("SELECT type FROM core.event_outbox WHERE type LIKE :p ORDER BY seq"), {"p": f"{prefix}%"}
        )
        return [r[0] for r in rows]


async def test_lifecycle(client: httpx.AsyncClient, support: SupportHarness, people: dict[str, UUID]) -> None:
    await login(client, "ursula")
    missing = await client.post("/api/v1/tickets", json={"type_key": "bug", "title": "Crash"})
    assert missing.status_code == 422 and missing.json()["code"] == "ticket.required_fields_missing"
    assert missing.json()["fields"] == ["steps"]
    created = await client.post(
        "/api/v1/tickets",
        json={
            "type_key": "bug",
            "title": "Player crashes",
            "description": "It crashes",
            "fields": {"steps": "Press play"},
        },
    )
    assert created.status_code == 201, created.text
    ticket = created.json()
    tid = ticket["id"]
    assert (
        ticket["state"] == "open"
        and ticket["reference"].startswith("T-")
        and {t["key"] for t in ticket["transitions"]} == {"cancel"}
    )
    await login(client, "sam")
    # one member's tickets only (their admin card)
    theirs = (await client.get(f"/api/v1/support/tickets?requester={people['ursula']}")).json()["items"]
    nobody = (await client.get(f"/api/v1/support/tickets?requester={people['sam']}")).json()["items"]
    assert [t["id"] for t in theirs] == [tid] and nobody == []
    assigned = await client.post(
        f"/api/v1/tickets/{tid}/assign", json={"assignee_id": str(people["sam"])}, headers={"If-Match": "1"}
    )
    assert assigned.status_code == 200 and assigned.json()["assignee_id"] == str(people["sam"])
    stale = await client.post(
        f"/api/v1/tickets/{tid}/transition", json={"transition": "start"}, headers={"If-Match": "1"}
    )
    assert stale.status_code == 409 and stale.json()["code"] == "ticket.version_conflict"
    started = await client.post(f"/api/v1/tickets/{tid}/transition", json={"transition": "start"})
    assert started.json()["state"] == "in_progress"
    needs_comment = await client.post(f"/api/v1/tickets/{tid}/transition", json={"transition": "ask_user"})
    assert needs_comment.status_code == 422
    await client.post(
        f"/api/v1/tickets/{tid}/transition", json={"transition": "ask_user", "comment": "Which version?"}
    )
    await client.post(f"/api/v1/tickets/{tid}/internal-notes", json={"body": "Probably the codec"})
    await login(client, "ursula")
    mine = (await client.get(f"/api/v1/tickets/{tid}")).json()
    assert [c["body"] for c in mine["comments"]] == ["Which version?"]  # internal note hidden
    assert all(h["kind"] != "comment_added" or not h["data"].get("internal") for h in mine["history"])
    forbidden = await client.post(f"/api/v1/tickets/{tid}/transition", json={"transition": "resolve"})
    assert forbidden.status_code == 403 and forbidden.json()["code"] == "ticket.transition_forbidden"
    await client.post(f"/api/v1/tickets/{tid}/transition", json={"transition": "respond", "comment": "1.2"})
    await login(client, "sam")
    resolved = await client.post(f"/api/v1/tickets/{tid}/transition", json={"transition": "resolve"})
    assert resolved.json()["state"] == "resolved"
    await login(client, "ursula")
    reopened = await client.post(f"/api/v1/tickets/{tid}/transition", json={"transition": "reopen"})
    assert reopened.json()["state"] == "open"
    await login(client, "sam")
    await client.post(f"/api/v1/tickets/{tid}/transition", json={"transition": "resolve"})
    closed = await client.post(f"/api/v1/tickets/{tid}/transition", json={"transition": "close"})
    assert closed.json()["state"] == "closed"
    seqs = [h["seq"] for h in closed.json()["history"]]
    assert seqs == list(range(1, len(seqs) + 1))
    with pytest.raises(Exception):  # noqa: B017 — append-only history
        async with support.full.database.unit_of_work() as uow:
            await uow.session.execute(text("UPDATE support.ticket_history SET kind = 'tag'"))
    events = await outbox(support, "ticket.")
    assert {
        "ticket.created",
        "ticket.assigned",
        "ticket.state_changed",
        "ticket.reopened",
        "ticket.resolved",
        "ticket.closed",
    } <= set(events)
    async with support.full.database.session() as session:
        audited = (
            (
                await session.execute(
                    text("SELECT action FROM audit.audit_entries WHERE action LIKE 'ticket.%'")
                )
            )
            .scalars()
            .all()
        )
    assert "ticket.closed_for_requester" in audited  # staff closed the requester's ticket
    categories = [r.category for r in support.outbox.sent]
    assert "support.ticket_status" in categories


async def test_precheck_incident_link_bulk(
    client: httpx.AsyncClient, support: SupportHarness, people: dict[str, UUID]
) -> None:
    incident, _ = await support.module.incidents.create(
        support.p("sam"), title="Media playback broken", severity="major", service_ids=["s1"]
    )

    class Wiki:
        async def search(self, text, principal, *, limit=5, for_ai=False):  # type: ignore[no-untyped-def]
            return [
                KnowledgeHit("portalab://wiki/1", "Fix playback", "Restart the app", "/wiki/fix-playback")
            ]

    await login(client, "ursula")
    body = {"service_id": "s1", "text": "the media playback does not start"}
    before = (await client.post("/api/v1/tickets/precheck", json=body)).json()
    assert (
        before["incidents"]["items"][0]["reference"].startswith("INC-")
        and before["knowledge"]["state"] == "unavailable"
    )
    support.full.identity.capabilities.provide(KNOWLEDGE, Wiki(), instance_ref="wiki", owner="test")
    after = (await client.post("/api/v1/tickets/precheck", json=body)).json()
    assert after["knowledge"]["items"][0]["title"] == "Fix playback"
    ids = []
    for title in ("Playback", "Playback again"):
        made = await client.post(
            "/api/v1/tickets",
            json={
                "type_key": "service_issue",
                "title": title,
                "service_id": "s1",
                "incident_id": str(incident.id),
            },
        )
        ids.append(made.json()["id"])
    assert made.json()["incident_reference"].startswith("INC-")
    assert (await client.post(f"/api/v1/tickets/{ids[0]}/merge", json={})).status_code in (
        404,
        405,
    )  # no merge
    await login(client, "sam")
    await support.module.incidents.resolve(support.p("sam"), incident.id, message="Fixed")
    states = [(await client.get(f"/api/v1/tickets/{i}")).json()["state"] for i in ids]
    assert states == ["open", "open"]  # resolving the incident never resolves tickets
    asked = await client.post(
        f"/api/v1/admin/incidents/{incident.id}/tickets/bulk",
        json={"comment": "Fixed by the incident", "transition": "resolve"},
    )
    assert asked.status_code == 409
    done = await client.post(
        f"/api/v1/admin/incidents/{incident.id}/tickets/bulk",
        json={
            "comment": "Fixed by the incident",
            "transition": "resolve",
            "confirmation": asked.json()["confirmation"],
        },
    )
    assert [r["ok"] for r in done.json()["results"]] == [True, True]
    assert {(await client.get(f"/api/v1/tickets/{i}")).json()["state"] for i in ids} == {"resolved"}
    async with support.full.database.session() as session:
        assert (
            await session.execute(
                text("SELECT count(*) FROM audit.audit_entries WHERE action = 'incident.tickets_bulk'")
            )
        ).scalar_one() == 1


async def test_feedback_and_conversion(
    client: httpx.AsyncClient, support: SupportHarness, people: dict[str, UUID]
) -> None:
    await login(client, "ursula")
    forms = {f["key"] for f in (await client.get("/api/v1/feedback/forms")).json()}
    assert forms == {"general", "bug_report", "feature_request"}
    bad = await client.post("/api/v1/feedback", json={"form_key": "bug_report", "values": {}})
    assert bad.status_code == 422 and bad.json()["fields"] == ["what"]
    sent = await client.post(
        "/api/v1/feedback",
        json={"form_key": "bug_report", "values": {"what": "Search is slow", "steps": "type"}},
    )
    fid = sent.json()["id"]
    assert (await client.get("/api/v1/me/tickets")).json() == []  # feedback never becomes a ticket by itself
    assert (await client.get("/api/v1/support/feedback")).status_code == 403
    await login(client, "sam")
    # one member's feedback only (their admin card)
    theirs = (await client.get(f"/api/v1/support/feedback?user_id={people['ursula']}")).json()
    nobody = (await client.get(f"/api/v1/support/feedback?user_id={people['sam']}")).json()
    assert [f["id"] for f in theirs] == [fid] and nobody == []
    detail = (await client.get(f"/api/v1/support/feedback/{fid}")).json()
    options = {c["target"]: (c["available"], c["reason"]) for c in detail["conversions"]}
    assert options["ticket"] == (True, None) and options["feature_proposal"] == (
        False,
        "community_unavailable",
    )
    assert options["contribution"] == (False, "permission")  # support may not credit contributions
    converted = await client.post(f"/api/v1/support/feedback/{fid}/convert", json={"target_kind": "ticket"})
    again = await client.post(f"/api/v1/support/feedback/{fid}/convert", json={"target_kind": "ticket"})
    assert converted.json()["ref"] == again.json()["ref"]  # once
    unavailable = await client.post(
        f"/api/v1/support/feedback/{fid}/convert", json={"target_kind": "feature_proposal"}
    )
    assert unavailable.status_code == 503 and unavailable.json()["code"] == "feedback.conversion_unavailable"
    await login(client, "ursula")
    mine = (await client.get("/api/v1/me/tickets")).json()
    assert [t["title"] for t in mine] == ["Search is slow"]  # requester keeps ownership; provenance kept
    granted: list[str] = []

    class Gamification:
        async def grant_contribution(self, user, kind, source_ref, actor):  # type: ignore[no-untyped-def]
            granted.append(source_ref)
            return f"contribution:{len(granted)}"

    support.full.identity.capabilities.provide(CONTRIBUTIONS, Gamification(), instance_ref="g", owner="test")
    await login(client, "boss")
    asked = await client.post(f"/api/v1/support/feedback/{fid}/convert", json={"target_kind": "contribution"})
    assert asked.status_code == 409
    token = asked.json()["confirmation"]
    await client.post(
        f"/api/v1/support/feedback/{fid}/convert", json={"target_kind": "contribution", "confirmation": token}
    )
    asked = await client.post(f"/api/v1/support/feedback/{fid}/convert", json={"target_kind": "contribution"})
    await client.post(
        f"/api/v1/support/feedback/{fid}/convert",
        json={"target_kind": "contribution", "confirmation": asked.json()["confirmation"]},
    )
    assert granted == [f"portalab://feedback/{fid}"]  # credited once
    second = await client.post(
        "/api/v1/feedback", json={"form_key": "general", "values": {"message": "hello"}}
    )
    await login(client, "sam")
    assert (await client.post(f"/api/v1/support/feedback/{second.json()['id']}/dismiss")).json()[
        "status"
    ] == "dismissed"


async def test_erasure(client: httpx.AsyncClient, support: SupportHarness, people: dict[str, UUID]) -> None:
    from portalab.capabilities.support import TicketRequest
    from portalab.modules.support.participant import SupportParticipant

    ticket = await support.module.tickets.create(
        support.p("ulrich"),
        TicketRequest(
            "access_request",
            "Need Books",
            "please",
            {"resource": "Books", "justification": "reading", "staff_notes": "x"},
        ),
    )
    await support.module.attachments.upload(support.p("ulrich"), ticket.id, b"plain text log\n", "log.txt")
    participant = SupportParticipant(support.full.database, support.module.blobs)
    exported = await participant.export(people["ulrich"])
    assert [r.category for r in exported] == ["support.ticket"]
    await participant.erase(people["ulrich"], "delete")  # type: ignore[arg-type]
    async with support.full.database.session() as session:
        row = (
            await session.execute(
                text("SELECT requester_id, fields FROM support.tickets WHERE id = :i"), {"i": ticket.id}
            )
        ).one()
        attachments = (await session.execute(text("SELECT count(*) FROM support.attachments"))).scalar_one()
        history = (
            await session.execute(
                text("SELECT count(*) FROM support.ticket_history WHERE ticket_id = :i"), {"i": ticket.id}
            )
        ).scalar_one()
    assert row[0] is None and "staff_notes" not in row[1] and attachments == 0 and history >= 2
