"""020 T031 — administration metrics never carry values or user identifiers; history redacts user refs."""

import pytest
from sqlalchemy import select

from portalab.modules.administration.models import SettingHistory
from portalab.modules.administration.observability import metrics
from tests.authz_fixtures import insert_user, user
from tests.integration.admin.settings_fixture import test_settings  # noqa: F401 — fixture
from tests.privacy_fixtures import FullPlatform

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("test_settings")]


async def test_metrics_and_history_redaction(full: FullPlatform) -> None:
    metrics.reset()
    member = await insert_user(full.database)
    await full.administration.config.set(
        "demo.theme", "dark-secret-choice", scope="user", scope_ref=str(member), actor=user(member)
    )
    snapshot = metrics.snapshot()
    assert snapshot["admin.config.changes"] == 1
    assert "dark-secret-choice" not in " ".join(snapshot) and str(member) not in " ".join(snapshot)
    async with full.database.session() as session:
        row = (await session.execute(select(SettingHistory))).scalar_one()
    assert row.scope_ref_hash != str(member) and len(row.scope_ref_hash) == 64
    with pytest.raises(ValueError):
        metrics.increment(f"admin.user.{member}")
