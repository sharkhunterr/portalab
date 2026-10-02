"""005 T036 (F14) — ``connector.sync`` / ``connector.action`` action types: declared permission and
idempotency, enforced for the automation's acting user."""

import pytest
from sqlalchemy import text

from portalab.core.db import Database
from portalab.core.errors import Forbidden
from tests.authz_fixtures import automation, insert_user
from tests.connectors_fixtures import ConnectorsHarness


async def test_actions_declared_and_enforced(database: Database, cn: ConnectorsHarness) -> None:
    sync, action = cn.actions.get("connector.sync"), cn.actions.get("connector.action")
    assert sync is not None and action is not None
    assert sync.permission == action.permission == "services.manage"
    assert sync.idempotency and action.idempotency and sync.owner == "module:connectors"

    service_id = await cn.enabled()
    assert cn.admin.user_id is not None
    params = {"service_id": str(service_id), "idempotency_ref": "rule-1:evt-9"}
    first = await sync.run(params, automation(cn.admin.user_id))
    again = await sync.run(params, automation(cn.admin.user_id))
    assert first["job_id"] == again["job_id"] and again["queued"] is False  # duplicate execution is harmless
    result = await action.run(
        {"service_id": str(service_id), "action": "refresh"}, automation(cn.admin.user_id)
    )
    assert result == {"result": {"refreshed": True}}

    member = await insert_user(database)
    with pytest.raises(Forbidden):  # an automation never exceeds its user
        await sync.run({"service_id": str(service_id)}, automation(member))
    async with database.session() as session:
        assert (
            await session.scalar(text("SELECT count(*) FROM core.job WHERE kind = 'connectors.sync_service'"))
            == 1
        )
