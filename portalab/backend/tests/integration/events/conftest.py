"""Events integration fixtures."""

from pathlib import Path

import pytest

from portalab.core.db import Database
from portalab.core.time import FixedClock
from tests.events_fixtures import EventsHarness, make_events
from tests.integration.privacy.conftest import NOW, app, client, full  # noqa: F401 — fixtures


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
async def ev(database: Database, tmp_path: Path, clock: FixedClock) -> EventsHarness:
    harness = make_events(database, tmp_path / "blobs", clock)
    await harness.full.authz.catalog.sync()
    return harness
