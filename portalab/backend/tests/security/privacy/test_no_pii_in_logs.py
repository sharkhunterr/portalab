"""021 T035 — privacy observability: counters for visibility decisions, overrides, retention, verification;
logs and metrics never carry user ids or data values."""

import io
import logging

import pytest

from portalab.core.authz_port import Principal
from portalab.core.logging import JsonFormatter
from portalab.modules.privacy.observability import metrics
from portalab.modules.privacy.policies.service import PolicyRequest
from tests.authz_fixtures import insert_user, user
from tests.privacy_fixtures import FullPlatform

pytestmark = pytest.mark.integration


async def test_metrics_and_logs(full: FullPlatform) -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logging.getLogger().addHandler(handler)
    try:
        metrics.reset()
        owner = await insert_user(full.database)
        await full.privacy.filter.filter(
            Principal(user_id=await insert_user(full.database)), owner, "profile_field", "bio", "SECRET-VALUE"
        )
        await full.privacy.policies.apply(
            user(owner), PolicyRequest("profile_field", "force_private", "r", subject_user_id=owner)
        )
        await full.privacy.policies.list_active()
        await full.privacy.retention.run()
    finally:
        logging.getLogger().removeHandler(handler)
    snapshot = metrics.snapshot()
    assert snapshot["privacy.visibility.private.hidden"] == 1
    assert snapshot["privacy.overrides.applied"] == 1 and snapshot["privacy.overrides.active"] == 1
    assert any(key.startswith("privacy.retention.") for key in snapshot)
    text = stream.getvalue() + " ".join(snapshot)
    assert "SECRET-VALUE" not in text and str(owner) not in " ".join(snapshot)
    with pytest.raises(ValueError):
        metrics.increment(f"privacy.user.{owner}")
