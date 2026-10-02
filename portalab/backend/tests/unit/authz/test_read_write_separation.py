"""003 T018 — read never implies create/modify/publish/delete; create/modify never imply publish."""

from uuid import uuid4

import pytest

from portalab.modules.authz.catalog.core_permissions import CORE_PERMISSIONS
from portalab.modules.authz.engine.engine import AuthorizationEngine, PermissionInfo
from portalab.modules.authz.grants.store import EffectiveGrants, GrantRow

pytestmark = pytest.mark.unit

ME = uuid4()
ACTIONS = ("create", "modify", "publish", "delete")


def _held(*keys: str) -> EffectiveGrants:
    return EffectiveGrants(
        ME, False, frozenset(), frozenset(), tuple(GrantRow(k, "allow", "global", "") for k in keys)
    )


def _allowed(key: str, held: EffectiveGrants) -> bool:
    return AuthorizationEngine._decide(PermissionInfo(key, True, False, False, False), held, ME, None).allowed


@pytest.mark.parametrize("domain", ["news", "wiki"])
def test_read_implies_nothing_else(domain: str) -> None:
    held = _held(f"{domain}.read")
    assert _allowed(f"{domain}.read", held)
    for action in (*ACTIONS, "edit"):
        assert not _allowed(f"{domain}.{action}", held)


def test_write_does_not_imply_publish_or_delete() -> None:
    held = _held("news.create", "news.modify")
    assert not _allowed("news.publish", held)
    assert not _allowed("news.delete", held)


def test_catalog_declares_distinct_content_actions() -> None:
    keys = {entry[0] for entry in CORE_PERMISSIONS}
    for key in (
        "news.read",
        "news.create",
        "news.modify",
        "news.publish",
        "news.delete",
        "wiki.read",
        "wiki.edit",
        "wiki.publish",
        "wiki.delete",
    ):
        assert key in keys
    sensitive = {entry[0] for entry in CORE_PERMISSIONS if entry[2]}
    assert {"news.publish", "news.delete", "wiki.publish", "wiki.delete"} <= sensitive
