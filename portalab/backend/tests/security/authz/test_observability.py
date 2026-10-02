"""003 T033 — authorization metrics/logs carry outcome kinds and permission keys only, never secrets,
tokens or user identifiers."""

import io
import logging

import pytest

from portalab.core.logging import JsonFormatter
from portalab.modules.authz.confirmation.service import ConfirmationService
from portalab.modules.authz.observability import metrics
from tests.authz_fixtures import AuthzPlatform, insert_user, make_admin, user

pytestmark = pytest.mark.integration


async def test_metrics_and_logs_hold_no_identifiers(platform: AuthzPlatform) -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        metrics.reset()
        admin, member = await insert_user(platform.database), await insert_user(platform.database)
        await make_admin(platform, admin)
        await platform.authz.engine.is_allowed(user(member), "users.manage")
        await platform.authz.engine.is_allowed(user(admin), "news.read")
        service = ConfirmationService(platform.database)
        token = await service.issue(user(admin), "news.delete", None, {})
        await service.consume(token, user(admin), "news.delete", None, {})
    finally:
        root.removeHandler(handler)
    snapshot = metrics.snapshot()
    assert snapshot["authz.decisions.deny"] >= 1 and snapshot["authz.decisions.allow"] >= 1
    assert snapshot["authz.sensitive_denials"] == 1
    assert snapshot["authz.confirmations.issued"] == snapshot["authz.confirmations.consumed"] == 1
    text = stream.getvalue() + " ".join(snapshot)
    for secret in (token, str(admin), str(member)):
        assert secret not in " ".join(snapshot)
    assert token not in text
    with pytest.raises(ValueError):
        metrics.increment(f"authz.user.{member}")
