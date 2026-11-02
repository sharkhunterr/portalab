"""010 T026/T027 — the e-mail channel: an outbox row per delivery (address hashed, never stored in clear),
sent by the job with backoff then ``failed`` after the attempt cap (a content-free failure event, the
portal item unaffected), ``no_address`` without a verified address, the body removed once sent, and the
SMTP adapter speaking real SMTP (aiosmtpd)."""

import asyncio
import dataclasses
import socket
from email import message_from_bytes
from email.policy import default
from typing import Any
from uuid import UUID

import httpx
import pytest
from aiosmtpd.controller import Controller
from fastapi import FastAPI
from sqlalchemy import text

from portalab.capabilities.notifications import CommunicationRequest, EmailMessage, Users, declare_category
from portalab.modules.notifications.channels.email import SmtpTransport, sender
from portalab.modules.notifications.settings import NotificationsConfig
from tests.authz_fixtures import make_admin
from tests.integration.identity.helpers import create_user, login, module_of
from tests.integration.notifications.conftest import NotifyHarness

pytestmark = pytest.mark.integration


async def with_email(notify: NotifyHarness, user: UUID, address: str) -> None:
    async with notify.database.unit_of_work() as uow:
        await uow.session.execute(
            text("UPDATE identity.users SET email = :e WHERE id = :u"), {"e": address, "u": user}
        )


async def deliveries(notify: NotifyHarness) -> dict[UUID, tuple[str, str, str | None, int]]:
    async with notify.database.session() as session:
        rows = await session.execute(
            text(
                "SELECT id, user_id, channel, status, suppress_reason, attempts"
                " FROM notify.deliveries WHERE channel = 'email'"
            )
        )
        return {r[0]: (str(r[1]), r[3], r[4], r[5]) for r in rows}


def request(users: tuple[UUID, ...], key: str) -> CommunicationRequest:
    return CommunicationRequest(
        category="media.new",
        template_key="notifications:service.unavailable",
        audience=Users(users),
        dedup_key=key,
        params={"service": "Media"},
        action_url="/media",
    )


async def test_email_outbox(app: FastAPI, notify: NotifyHarness) -> None:
    declare_category(
        "media.new",
        "module:media",
        "media:category",
        default_channels=("portal", "email"),
        registry=notify.categories,
    )
    notify.module.config = dataclasses.replace(notify.module.config, email_enabled=True, email_max_attempts=2)
    alex = await create_user(module_of(app), "alex")
    sam = await create_user(module_of(app), "sam")
    await with_email(notify, alex, "alex@example.test")
    await notify.module.send(request((alex, sam), "e1"))
    rows = await deliveries(notify)
    by_user = {v[0]: (k, v) for k, v in rows.items()}
    assert by_user[str(sam)][1][1:3] == ("suppressed", "no_address")
    alex_delivery = by_user[str(alex)][0]
    async with notify.database.session() as session:
        stored = (await session.execute(text("SELECT to_hash, body_text FROM notify.email_outbox"))).one()
    assert "@" not in stored[0] and "/media" in stored[1]  # hash only; the link is part of the body
    notify.mail.fail = 1
    await notify.module.email.run({"delivery": str(alex_delivery)})  # first attempt fails, retried later
    assert (await deliveries(notify))[alex_delivery][1:] == ("pending", None, 1)
    await notify.module.email.run({"delivery": str(alex_delivery)})
    assert (await deliveries(notify))[alex_delivery][1] == "sent"
    assert [m.to for m in notify.mail.sent] == ["alex@example.test"]
    async with notify.database.session() as session:
        assert (await session.execute(text("SELECT count(*) FROM notify.email_outbox"))).scalar_one() == 0
    await notify.module.send(request((alex,), "e2"))
    second = next(k for k, v in (await deliveries(notify)).items() if v[1] == "pending")
    notify.mail.fail = 5
    for _ in range(2):
        await notify.module.email.run({"delivery": str(second)})
    assert (await deliveries(notify))[second][1:] == ("failed", None, 2)
    async with notify.database.session() as session:
        events = (
            (
                await session.execute(
                    text(
                        "SELECT payload::text FROM events.events WHERE type = 'notification.delivery_failed'"
                    )
                )
            )
            .scalars()
            .all()
        )
        portal = (
            await session.execute(
                text("SELECT count(*) FROM notify.notifications WHERE user_id = :u"), {"u": alex}
            )
        ).scalar_one()
    assert events and all("alex" not in e and "Media" not in e for e in events)
    assert portal == 2  # the portal channel is independent of e-mail failures


class Sink:
    def __init__(self) -> None:
        self.messages: list[Any] = []

    async def handle_DATA(self, server: Any, session: Any, envelope: Any) -> str:
        self.messages.append(envelope)
        return "250 OK"


async def test_smtp_adapter() -> None:
    sink = Sink()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    controller = Controller(sink, hostname="127.0.0.1", port=port)
    controller.start()
    try:
        config = NotificationsConfig(smtp_host="127.0.0.1", smtp_port=port)

        async def no_password() -> str:
            return ""

        async def named() -> str:
            return "Xénoportal"

        transport = SmtpTransport(lambda: config, no_password, named)
        await transport.send(EmailMessage("alex@example.test", "Subject\ninjected", "Hello", "<p>Hello</p>"))
        await asyncio.sleep(0)
    finally:
        controller.stop()
    assert len(sink.messages) == 1
    envelope = sink.messages[0]
    assert envelope.rcpt_tos == ["alex@example.test"]
    parsed = message_from_bytes(envelope.content)
    assert parsed["Subject"] == "Subject injected"  # no header injection
    assert parsed.is_multipart()
    # #339: the sender's name, as mail clients show it
    named = message_from_bytes(envelope.content, policy=default)
    assert str(named["From"]) == "Xénoportal <portalab@localhost>"


def test_sender_name() -> None:
    """#339: a name with the address; none (or an address it cannot carry): the bare address."""
    assert str(sender("  Xeno   portal ", "a@b.test")) == "Xeno portal <a@b.test>"
    assert sender("", "a@b.test") == "a@b.test"
    assert sender("Xeno", "not an address") == "not an address"


async def test_members_email_switched_off_but_the_administrators(
    app: FastAPI, client: httpx.AsyncClient, notify: NotifyHarness
) -> None:
    """#318: one action switches the e-mails off in every member's own preferences — the administrators keep
    theirs, a mandatory channel stays; the members' digest goes off; each may change theirs again."""
    declare_category(
        "media.new",
        "module:media",
        "media:category",
        default_channels=("portal", "email"),
        registry=notify.categories,
    )
    boss = await create_user(module_of(app), "boss")
    await make_admin(notify.ev.full, boss)
    await create_user(module_of(app), "alex")
    await login(client, "boss")
    done = await client.put("/api/v1/admin/notifications/members/email", json={"enabled": False})
    assert done.status_code == 200 and done.json() == {"changed": 1, "kept": 1}
    await login(client, "alex")
    mine = (await client.get("/api/v1/me/notification-preferences")).json()
    media = next(c for c in mine["categories"] if c["key"] == "media.new")
    assert media["channels"]["email"]["enabled"] is False and media["channels"]["portal"]["enabled"] is True
    assert mine["digest"] == "off"
    await login(client, "boss")
    own = (await client.get("/api/v1/me/notification-preferences")).json()
    assert (
        next(c for c in own["categories"] if c["key"] == "media.new")["channels"]["email"]["enabled"] is True
    )
    await login(client, "alex")  # a plain member cannot do it
    assert (
        await client.put("/api/v1/admin/notifications/members/email", json={"enabled": True})
    ).status_code == 403
