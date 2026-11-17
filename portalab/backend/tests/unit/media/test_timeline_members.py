"""Issue 484 — the activity chart by member: a household's members by name (its profiles too), the most active
eight then the others together, the plays nobody is linked to apart; for a member on the server, « you » and
« the other members » only."""

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from portalab.core.authz_port import Principal
from portalab.modules.media.api.router import _timeline_members
from portalab.modules.media.insights.aggregate import NIL


class Directory:
    def __init__(self, names: dict[UUID, str]) -> None:
        self.names = names

    async def get_user_summary(self, user: UUID) -> Any:
        return SimpleNamespace(display_name=self.names.get(user))


def module(names: dict[UUID, str]) -> Any:
    provider = SimpleNamespace(provider=Directory(names))
    return SimpleNamespace(capabilities=SimpleNamespace(system_providers=lambda _: [provider]))


def data(members: dict[str, float]) -> dict[str, Any]:
    return {
        "timeline": {
            "unit": "day",
            "points": [
                {
                    "date": "2026-11-16",
                    "members": {k: {"seconds": s, "plays": 1} for k, s in members.items()},
                },
                {"date": "2026-11-17", "seconds": {}, "plays": 0},  # a day without activity
            ],
        }
    }


async def test_a_household_by_name_the_most_active_first() -> None:
    zoe, lea = uuid4(), uuid4()
    others = [uuid4() for _ in range(8)]
    seconds = {
        str(zoe): 900.0,
        str(lea): 3600.0,
        NIL: 60.0,
        **{str(u): 10.0 + i for i, u in enumerate(others)},
    }
    found = data(seconds)
    await _timeline_members(module({zoe: "Zoé", lea: "Léa"}), Principal(user_id=zoe), found, named=True)
    members = found["timeline"]["members"]
    assert [m["key"] for m in members[:2]] == [str(lea), str(zoe)]  # the most active first
    assert members[0]["name"] == "Léa" and members[1]["name"] == "Zoé" and members[1]["me"] is True
    assert [m["key"] for m in members[-2:]] == ["others", "unattributed"]  # past eight, together
    assert len(members) == 8 + 2
    day = found["timeline"]["points"][0]["members"]
    assert day["others"] == {"seconds": 10.0 + 11.0, "plays": 2}  # the two least active
    assert found["timeline"]["points"][1]["members"] == {}


async def test_the_server_for_a_member_is_you_and_the_others() -> None:
    me, a, b = uuid4(), uuid4(), uuid4()
    found = data({str(me): 100.0, str(a): 50.0, str(b): 70.0})
    await _timeline_members(module({a: "Alice", b: "Bob"}), Principal(user_id=me), found, named=False)
    assert found["timeline"]["members"] == [
        {"key": "me", "name": None, "me": True},
        {"key": "others", "name": None, "me": False},
    ]
    assert found["timeline"]["points"][0]["members"]["others"] == {"seconds": 120.0, "plays": 2}
