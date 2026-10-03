"""015 T004 — schema: tables and constraints, append-only state history, funding rules immutable once the
project is open, FKs only intra-module or to ``identity.users``."""

import pytest
from sqlalchemy import text

from portalab.core.errors import Conflict, ValidationFailed
from tests.integration.marketplace.conftest import RULES, MkHarness

pytestmark = pytest.mark.integration


async def test_schema(mk: MkHarness) -> None:
    project = await mk.project(open_with=RULES)
    async with mk.database.session() as session:
        tables = set(
            (
                await session.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname = 'marketplace'")
                )
            ).scalars()
        )
        foreign = set(
            (
                await session.execute(
                    text(
                        "SELECT confrelid::regclass::text FROM pg_constraint c JOIN pg_namespace n "
                        "ON n.oid = c.connamespace WHERE n.nspname = 'marketplace' AND contype = 'f'"
                    )
                )
            ).scalars()
        )
    assert {"projects", "project_state_history", "project_fundings", "project_notes"} <= tables
    assert all(f == "identity.users" or f.startswith("marketplace.") for f in foreign)
    async with mk.database.session() as session:
        with pytest.raises(Exception, match="append-only"):
            await session.execute(text("UPDATE marketplace.project_state_history SET reason = 'x'"))
    with pytest.raises(Conflict):
        await mk.module.transition(mk.p("boss"), project, "open", rules=RULES)  # not from open
    with pytest.raises(ValidationFailed):
        await mk.module.transition(mk.p("boss"), project, "validation", rules={"min_funding": 1})
    async with mk.database.session() as session:
        rules = await session.scalar(
            text("SELECT funding_rules FROM marketplace.projects WHERE id = :i"), {"i": project}
        )
    assert rules["min_funding"] == 5 and rules["refund_on_reject"] == 100
