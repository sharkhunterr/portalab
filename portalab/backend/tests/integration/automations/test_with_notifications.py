"""019 T033 — with the real 010 module: ``communication.produce`` delivers through the producer; the 014
announcement preset validates against the real ``campaign.*`` event types once both are registered."""

import pytest
from sqlalchemy import text

from portalab.capabilities.notifications import CategoryRegistry
from portalab.capabilities.observability import ObservableRegistry
from portalab.modules.automations.templates.loader import load
from portalab.modules.campaigns.events import register_event_types as register_campaign_events
from portalab.modules.notifications.module import NotificationsModule
from tests.integration.automations.conftest import AutoHarness, basic

pytestmark = pytest.mark.integration


async def test_communication_through_notifications(au: AutoHarness) -> None:
    categories = CategoryRegistry()
    notifications = NotificationsModule(
        au.database,
        au.ev.publisher,
        au.ev.full.authz.audit,
        au.ev.full.identity.capabilities,
        au.ev.full.authz.engine,
        clock=au.clock,
        categories=categories,
        event_types=au.ev.types,
        consumers=au.ev.consumers,
        observables=ObservableRegistry(),
        actions=au.actions,
    )
    notifications.register()
    from portalab.capabilities.notifications import declare_category

    declare_category(
        "automations.message", "module:automations", "automations:category.message", registry=categories
    )
    automation = await au.automation(
        "welcome",
        basic(
            conditions=None,
            steps=[
                {
                    "id": "send",
                    "action": "communication.produce",
                    "params": {
                        "category": "automations.message",
                        "template_key": "automations:notify.message",
                        "audience": {"type": "users", "ids": ["${actor.id}"]},
                        "dedup_key": "welcome:${actor.id}",
                        "params": {"text": "Welcome"},
                    },
                }
            ],
        ),
    )
    await au.emit({"value": 1})
    assert [e.status for e in await au.executions(automation)] == ["success"]
    async with au.database.session() as session:
        delivered = await session.scalar(
            text("SELECT count(*) FROM notify.notifications WHERE user_id = :u"), {"u": au.people["ursula"]}
        )
    assert delivered == 1
    register_campaign_events(au.ev.types)
    preset = next(t for t in load() if t.key == "campaign-start-announcement")
    assert au.module.definitions.validate(preset.definition).trigger.event_type == "campaign.started"
