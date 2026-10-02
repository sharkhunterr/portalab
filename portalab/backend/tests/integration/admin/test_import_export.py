"""020 T019 — export excludes sensitive values and carries ``format_version``; import validates, reports
conflicts (never silently overwrites) and applies only confirmed conflicts; audited."""

import pytest
from sqlalchemy import select

from portalab.modules.authz.models import AuditEntry
from tests.authz_fixtures import insert_user, user
from tests.integration.admin.settings_fixture import test_settings  # noqa: F401 — fixture
from tests.privacy_fixtures import FullPlatform

pytestmark = pytest.mark.usefixtures("test_settings")


async def test_round_trip_with_conflicts(full: FullPlatform) -> None:
    admin = user(await insert_user(full.database))
    config, io = full.administration.config, full.administration.import_export
    await config.set("demo.pageSize", 40, actor=admin)
    await config.set("demo.apiToken", "hidden-value", actor=admin)
    document = await io.export(admin)
    assert document["format_version"] == 1
    assert [entry["key"] for entry in document["settings"]] == ["demo.pageSize"]
    assert "hidden-value" not in str(document)

    await config.set("demo.pageSize", 25, actor=admin)  # the portal changed meanwhile
    report = await io.import_(admin, document, accept_conflicts=[])
    assert (
        report.applied == []
        and report.conflicts[0]["current"] == 25
        and report.conflicts[0]["incoming"] == 40
    )
    assert (await config.get("demo.pageSize")).value == 25  # not overwritten
    report = await io.import_(admin, document, accept_conflicts=[report.conflicts[0]["id"]])
    assert report.applied == ["demo.pageSize"] and (await config.get("demo.pageSize")).value == 40

    bad = {
        "format": "portalab.configuration",
        "format_version": 1,
        "settings": [{"key": "demo.pageSize", "value": "x"}, {"key": "demo.apiToken", "value": "y"}],
    }
    report = await io.import_(admin, bad, accept_conflicts=[])
    assert {error["key"] for error in report.errors} == {
        "demo.pageSize",
        "demo.apiToken",
    } and report.applied == []
    with pytest.raises(Exception, match="Unsupported"):
        await io.import_(admin, {"format": "other"}, accept_conflicts=[])
    async with full.database.session() as session:
        actions = (await session.execute(select(AuditEntry.action))).scalars().all()
    assert "admin.export_performed" in actions and actions.count("admin.import_performed") == 3
