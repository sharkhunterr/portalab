"""027 T067 — ``dashboard_0002`` back-fills grid coordinates from ordered dashboards: same widgets, sizes and
configurations, active widgets first in their order, no overlap, everything inside the 12 columns."""

import asyncio
import json
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.pool import NullPool

from portalab.app.migrations import upgrade
from portalab.core.db import Database
from tests.authz_fixtures import insert_user

INSERT = text(
    "INSERT INTO dashboard.widget_instances (id, user_id, widget_key, status, position, w, h, config, "
    "config_schema_version, origin, created_at, updated_at) VALUES (:id, :user, :key, :status, :position, "
    ":w, :h, CAST(:config AS jsonb), 1, 'user', now(), now())"
)
ROWS = [  # (status, position, w, h) — an ordered 009 dashboard
    ("active", 0, 4, 2),
    ("active", 1, 4, 1),
    ("hidden", 2, 6, 2),
    ("active", 3, 6, 2),
    ("active", 4, 12, 1),
    ("active", 5, 3, 1),
]


async def test_ordered_dashboards_are_flowed_into_the_grid(empty_db_url: str) -> None:
    await asyncio.to_thread(upgrade, empty_db_url, "dashboard_0001")
    db = Database.from_url(empty_db_url, poolclass=NullPool)
    try:
        users = [await insert_user(db), await insert_user(db)]
        async with db.engine.begin() as conn:
            for user in users:
                for index, (status, position, w, h) in enumerate(ROWS):
                    await conn.execute(
                        INSERT,
                        {
                            "id": uuid4(),
                            "user": user,
                            "key": f"t.w{index}",
                            "status": status,
                            "position": position,
                            "w": w,
                            "h": h,
                            "config": json.dumps({"n": index}),
                        },
                    )
        await asyncio.to_thread(upgrade, empty_db_url, "dashboard_0002")
        async with db.engine.connect() as conn:
            for user in users:
                rows = (
                    await conn.execute(
                        text(
                            "SELECT widget_key, status, x, y, w, h, config FROM dashboard.widget_instances "
                            "WHERE user_id = :u ORDER BY widget_key"
                        ),
                        {"u": user},
                    )
                ).all()
                assert len(rows) == len(ROWS)
                assert [(r.w, r.h) for r in rows] == [(w, h) for _, _, w, h in ROWS]
                assert [r.config for r in rows] == [{"n": i} for i in range(len(ROWS))]
                cells = {(r.widget_key): (r.x, r.y) for r in rows}
                assert cells["t.w0"] == (0, 0) and cells["t.w1"] == (4, 0) and cells["t.w3"] == (0, 2)
                assert cells["t.w4"] == (0, 4) and cells["t.w5"] == (0, 5)
                active = [r for r in rows if r.status == "active"]
                for a in active:
                    assert a.x >= 0 and a.x + a.w <= 12 and a.y >= 0
                    for b in active:
                        if a.widget_key < b.widget_key:
                            assert not (
                                a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h
                            ), (a, b)
    finally:
        await db.dispose()
