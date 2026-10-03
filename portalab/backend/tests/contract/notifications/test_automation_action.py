"""010 T023 — the ``communication.produce`` action, run as a fake engine would (019): registered with its
permission and idempotency; it acts under the author's authority (an author cannot target an audience they
cannot see); a duplicate trigger yields one communication."""

import pytest
from fastapi import FastAPI

from portalab.capabilities.notifications import declare_category
from portalab.modules.notifications.automation import KEY
from portalab.modules.notifications.permissions import SEND_TO_AUDIENCE
from portalab.modules.notifications.producer.service import AudienceForbidden
from tests.authz_fixtures import automation, make_admin
from tests.integration.identity.helpers import create_user, module_of
from tests.integration.notifications.conftest import NotifyHarness

pytestmark = pytest.mark.integration


async def test_automation_action(app: FastAPI, notify: NotifyHarness) -> None:
    declare_category("media.new", "module:media", "media:category", registry=notify.categories)
    action = notify.actions.get(KEY)
    assert action is not None and action.permission == SEND_TO_AUDIENCE and action.idempotency
    alex = await create_user(module_of(app), "alex")
    boss = await create_user(module_of(app), "boss")
    await make_admin(notify.ev.full, boss)
    params = {
        "category": "media.new",
        "template_key": "notifications:service.unavailable",
        "audience": {"type": "permission", "permission": "audit.read"},
        "dedup_key": "rule-1:trigger-9",
        "params": {"service": "Media"},
    }
    first = await action.run(params, automation(boss))
    again = await action.run(params, automation(boss))
    assert first["created"] and not again["created"] and first["communication"] == again["communication"]
    assert first["recipients"] == 1  # only the admin holds audit.read
    with pytest.raises(AudienceForbidden):
        await action.run({**params, "dedup_key": "rule-2:t"}, automation(alex))  # author-bounded
    with pytest.raises(AudienceForbidden):
        await action.run(
            {**params, "dedup_key": "rule-3:t", "audience": {"type": "users", "ids": [str(boss)]}},
            automation(alex),
        )
    mine = await action.run(
        {**params, "dedup_key": "rule-4:t", "audience": {"type": "users", "ids": [str(alex)]}},
        automation(alex),
    )
    assert mine["created"]
