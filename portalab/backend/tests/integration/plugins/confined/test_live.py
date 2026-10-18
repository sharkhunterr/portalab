"""030 T046 (US3) — live channels for a plugin: only its declared topics, under its own name, to the members
it names (or holders of one of its own permissions), bounded in size and rate."""

from uuid import uuid4

import pytest
from sqlalchemy import select
from tests.integration.plugins.conftest import PlHarness

from portalab.core.live import LiveEvent
from portalab.modules.plugins.confined.host import Denied
from portalab.modules.plugins.confined.services import Services
from portalab.modules.plugins.manifest.schema import validate

MANIFEST = validate(
    {
        "schema_version": 2,
        "key": "messenger",
        "name": "Messenger",
        "version": "1.0.0",
        "entry_point": "messenger_plugin:register",
        "capabilities": {"live": {"topics": ["new"]}},
    }
)
GRANT = {"topics": ["new"]}


async def test_live_messages_reach_the_named_members_only(pl: PlHarness) -> None:
    services = Services(pl.database, None, None)
    a, b = uuid4(), uuid4()
    sent = await services.live(
        "messenger", MANIFEST, GRANT, {"topic": "new", "payload": {"c": 1}, "users": [str(a), str(b)]}, None
    )
    assert sent == {"delivered": 2}
    async with pl.database.session() as session:
        rows = list(
            (
                await session.execute(select(LiveEvent).where(LiveEvent.topic == "plugin.messenger.new"))
            ).scalars()
        )
    assert {r.audience_user_id for r in rows} == {a, b} and all(r.payload == {"c": 1} for r in rows)

    for args, code in (
        ({"topic": "other", "payload": {}}, "denied"),
        ({"topic": "new", "payload": {}, "permission": "admin.access"}, "denied"),
        ({"topic": "new", "payload": {"x": "y" * 9000}, "users": [str(a)]}, "oversize"),
    ):
        with pytest.raises(Denied) as error:
            await services.live("messenger", MANIFEST, GRANT, args, None)
        assert error.value.code == code

    services._live.burst, services._live.rate = 2, 0.0
    services._live._state.clear()
    for _ in range(2):
        await services.live(
            "messenger", MANIFEST, GRANT, {"topic": "new", "payload": {}, "users": [str(a)]}, None
        )
    with pytest.raises(Denied) as flood:
        await services.live(
            "messenger", MANIFEST, GRANT, {"topic": "new", "payload": {}, "users": [str(a)]}, None
        )
    assert flood.value.code == "rate"
