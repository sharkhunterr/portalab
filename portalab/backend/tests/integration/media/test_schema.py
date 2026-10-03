"""024 T005 — schema ``media``: unique strong ids and source items, append-only merge log, and foreign keys
only inside the module or to ``identity.users``."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from portalab.core.db import Database

pytestmark = pytest.mark.integration
OBJECT = "00000000-0000-7000-8000-0000000000a1"


async def test_schema(database: Database) -> None:
    async with database.session() as session:
        targets = {
            r[0]
            for r in await session.execute(
                text(
                    "SELECT DISTINCT ccu.table_schema || '.' || ccu.table_name"
                    " FROM information_schema.table_constraints tc"
                    " JOIN information_schema.constraint_column_usage ccu"
                    " ON tc.constraint_name = ccu.constraint_name"
                    " WHERE tc.table_schema = 'media' AND tc.constraint_type = 'FOREIGN KEY'"
                )
            )
        }
    assert targets and all(t.startswith("media.") or t == "identity.users" for t in targets)
    async with database.unit_of_work() as uow:
        await uow.session.execute(
            text(
                "INSERT INTO media.objects (id, kind, title, sort_title, available, effective,"
                " field_provenance, status, first_seen_at, created_at, updated_at)"
                " VALUES (:id, 'movie', 'x', 'x', false, '{}', '{}', 'active', now(), now(), now())"
            ),
            {"id": OBJECT},
        )
        await uow.session.execute(
            text("INSERT INTO media.external_ids VALUES ('tmdb', '1', :id)"),
            {"id": OBJECT},
        )
        await uow.session.execute(
            text(
                "INSERT INTO media.merge_log (id, action, object_id, other_id, details, created_at) VALUES"
                " (gen_random_uuid(), 'merge', gen_random_uuid(), gen_random_uuid(), '{}', now())"
            )
        )
    with pytest.raises(IntegrityError):
        async with database.unit_of_work() as uow:
            await uow.session.execute(
                text("INSERT INTO media.external_ids VALUES ('tmdb', '1', :id)"),
                {"id": OBJECT},
            )
    for statement in ("UPDATE media.merge_log SET action = 'split'", "DELETE FROM media.merge_log"):
        with pytest.raises(DBAPIError):
            async with database.unit_of_work() as uow:
                await uow.session.execute(text(statement))
