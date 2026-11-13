"""Issue 398 — an e-mail says more than its title: the facts its template labels (a level's XP, an incident's
severity and start), the rewards won as chips, the words someone wrote set apart (escaped, never a link), the
moments in the reader's language rather than raw ISO, a text by language in the reader's, the plain-text part
with the same facts and an absolute link; and what the parameters say goes with the account it was for."""

import dataclasses
from collections.abc import Mapping
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from sqlalchemy import text

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.notifications import CommunicationRequest, Users, declare_category
from portalab.capabilities.retention import default_retention_targets
from portalab.modules.notifications.fanout.service import _in_language
from portalab.modules.notifications.participant import NotificationsParticipant
from tests.integration.identity.helpers import create_user, module_of
from tests.integration.notifications.conftest import NotifyHarness
from tests.integration.notifications.test_email import with_email

pytestmark = pytest.mark.integration


async def mailed(notify: NotifyHarness, key: str) -> tuple[str, str, str]:
    async with notify.database.session() as session:
        row = (
            await session.execute(
                text(
                    "SELECT o.subject, o.body_text, o.body_html FROM notify.email_outbox o"
                    " JOIN notify.deliveries d ON d.id = o.delivery_id"
                    " JOIN notify.communications c ON c.id = d.communication_id WHERE c.dedup_key = :k"
                ),
                {"k": key},
            )
        ).one()
    return row[0], row[1], row[2]


def send(user: UUID, key: str, template: str, params: Mapping[str, Any], url: str) -> CommunicationRequest:
    return CommunicationRequest(
        category="test.mail",
        template_key=template,
        audience=Users((user,)),
        dedup_key=key,
        params=dict(params),
        action_url=url,
    )


async def test_an_email_tells_the_facts_rewards_and_words_of_its_notification(
    app: FastAPI, notify: NotifyHarness
) -> None:
    declare_category(
        "test.mail", "module:test", "notifications:category", default_channels=("portal", "email"),
        registry=notify.categories,
    )  # fmt: skip
    notify.module.config = dataclasses.replace(
        notify.module.config, email_enabled=True, portal_url="https://portal.example"
    )
    alex = await create_user(module_of(app), "alex")
    await with_email(notify, alex, "alex@example.test")

    level = {
        "level": 8,
        "total_xp": 1234,
        "to_next": 166,
        "next_level": 9,
        "coins": 50,
        "gifts": "Gold frame",
    }
    await notify.module.send(send(alex, "lvl", "gamification:notify.level_up", level, "/progression"))
    subject, plain, html = await mailed(notify, "lvl")
    assert subject == "Level up! You reached level 8."
    for shown in ("Total XP", "1,234", "To level 9", "166 XP", "+50 Coins", "Unlocked", "Gold frame"):
        assert shown in html, shown
    assert "Total XP: 1,234" in plain and "+50 Coins" in plain
    assert "https://portal.example/progression" in plain  # the plain text's link is whole

    incident = {
        "number": "INC-0013",
        "title": "SUB/WAVE is not responding",
        "severity": "major",
        "state": "monitoring",
        "summary": "none",
        "quote": "Fixed by a restart, see https://evil.example/login <b>now</b>",
        "created_at": "2026-11-12T07:30:00+00:00",
        "resolved_at": "none",
    }
    await notify.module.send(send(alex, "inc", "support:incident.updated", incident, "/incidents/x"))
    _, plain, html = await mailed(notify, "inc")
    assert "Severity" in html and "Major" in html and "Monitoring" in html and "Started" in html
    assert "2026-11-12T07:30" not in html and "2026" in html  # a moment, in words
    assert "<b>now</b>" not in html and "&lt;b&gt;now&lt;/b&gt;" in html
    assert 'href="https://evil.example' not in html  # what someone wrote never becomes a link
    assert "Resolved" not in html  # « none »: nothing to say
    assert "« Fixed by a restart" in plain

    names = {"en": "Winter festival", "fr": "Fête d'hiver"}
    await notify.module.send(
        send(alex, "camp", "campaigns:notify.announcement", {"campaign": names, "message": "Come!"}, "/c")
    )
    subject, _, _ = await mailed(notify, "camp")
    assert subject == "Winter festival has started!"
    assert _in_language(names, LocaleContext(language="fr")) == "Fête d'hiver"
    assert _in_language(names, LocaleContext(language="de")) == "Winter festival"

    # the parameters go with the deliveries (retention: the target's own SQL, while they remain then once
    # gone) and with the account they were for (erasure)
    target = next(t for t in default_retention_targets.all() if t.name == "notifications.communications")
    purge = f"DELETE FROM notify.communications WHERE {target.extra_condition}"  # constant SQL
    async with notify.database.unit_of_work() as uow:  # still referenced: kept
        assert getattr(await uow.session.execute(text(purge)), "rowcount", None) == 0
    sam = await create_user(module_of(app), "sam")
    await notify.module.send(send(sam, "sam", "campaigns:notify.announcement", {"campaign": "x"}, "/c"))
    await NotificationsParticipant(notify.database).erase(alex, "final")
    async with notify.database.session() as session:
        left = (await session.execute(text("SELECT dedup_key FROM notify.communications"))).scalars().all()
    assert left == ["sam"]  # alex's alone are gone, sam's stays
