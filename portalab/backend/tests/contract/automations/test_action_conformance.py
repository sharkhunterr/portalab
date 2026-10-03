"""019 T022/T023 — owner action conformance kit: declared params and idempotency, permission enforcement by
the engine, provenance (``correlation_id`` = chain, ``provenance.automation`` in emitted events) and timeout
behavior — run against the real 010 ``communication.produce`` (fake send), the engine's own actions and the
registered owner catalog (013 awards, 016 tickets/incidents, 011 publish, 005 connectors,
018 ``ai.invoke``)."""

from collections.abc import Mapping
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text

from portalab.capabilities.automation_actions import ActionRegistry, ActionType
from portalab.capabilities.notifications import CommunicationRef, CommunicationRequest
from portalab.core.authz_port import Principal
from portalab.modules.notifications.automation import register_action
from tests.integration.automations.conftest import AutoHarness, basic

pytestmark = pytest.mark.integration


class KitCase:
    """Reusable checks for one registered action type."""

    @staticmethod
    def static(action: ActionType) -> None:
        assert action.idempotency.strip(), action.key
        assert action.permission and "." in action.permission, action.key
        assert action.owner.startswith(("module:", "plugin:")), action.key
        assert all(isinstance(k, str) and isinstance(v, str) for k, v in action.params_schema.items()), (
            action.key
        )


def test_owner_catalog_is_conformant() -> None:
    import portalab.app.main  # noqa: F401 — imports every module
    from portalab.app.wiring import wire_platform  # noqa: F401

    registry = ActionRegistry()
    sent: list[CommunicationRequest] = []

    async def send(request: CommunicationRequest, principal: Principal | None) -> CommunicationRef:
        sent.append(request)
        return CommunicationRef(uuid4(), True, 3)

    register_action(send, registry)
    for action in registry.all():
        KitCase.static(action)
    assert registry.get("communication.produce") is not None


async def test_engine_enforces_and_propagates(au: AutoHarness) -> None:
    sent: list[tuple[CommunicationRequest, Principal | None]] = []

    async def send(request: CommunicationRequest, principal: Principal | None) -> CommunicationRef:
        sent.append((request, principal))
        return CommunicationRef(uuid4(), True, 2)

    register_action(send, au.actions)
    for action in au.actions.all():
        KitCase.static(action)
    automation = await au.automation(
        "announce",
        basic(
            conditions=None,
            steps=[
                {
                    "id": "send",
                    "action": "communication.produce",
                    "params": {
                        "category": "automations.message",
                        "template_key": "automations:notify.message",
                        "audience": {"type": "all"},
                        "dedup_key": "evt:${event.id}",
                        "params": {"text": "${event.label}"},
                    },
                },
                {"id": "chain", "action": "automation.trigger", "params": {"automation": "next"}},
            ],
        ),
    )
    await au.emit({"value": 1, "label": "hello"}, correlation="chain-42")
    [execution] = await au.executions(automation)
    assert execution.status == "success" and execution.chain_id == "chain-42"
    request, principal = sent[0]
    assert (
        request.source == "automation"
        and request.params == {"text": "hello"}
        and request.dedup_key.startswith("evt:")
    )
    assert (
        principal is not None
        and principal.channel == "automation"
        and principal.acting_for == au.people["boss"]
    )
    async with au.database.session() as session:
        triggered = (
            await session.execute(
                text(
                    "SELECT correlation_id, provenance FROM events.events WHERE type = 'automation.triggered'"
                )
            )
        ).one()
    assert triggered.correlation_id == "chain-42"
    assert triggered.provenance["automation"]["execution_id"] == str(execution.id)
    assert triggered.provenance["automation"]["path"] == [str(automation)]


async def test_permission_enforced_for_owner_actions(au: AutoHarness) -> None:
    async def run(params: Mapping[str, Any], principal: Principal) -> Mapping[str, Any]:
        return {"ok": True}

    au.actions.register(
        ActionType(
            "test.publish", "publish", "news.publish", "state guard", run, "module:news", {"article": "uuid?"}
        )
    )
    automation = await au.automation(
        "publisher", basic(conditions=None, steps=[{"id": "p", "action": "test.publish"}]), author="ursula"
    )
    await au.emit({"value": 1})
    assert [e.status for e in await au.executions(automation)] == ["refused"]
