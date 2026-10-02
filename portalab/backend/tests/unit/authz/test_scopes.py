"""003 T017 — scopes: ``self`` only own objects; ``owned`` needs owner_id; service A never applies to B;
module scope does not cross modules."""

from uuid import uuid4

import pytest

from portalab.core.authz_port import ResourceRef
from portalab.modules.authz.engine.scopes import scope_matches

pytestmark = pytest.mark.unit

ME, OTHER = uuid4(), uuid4()


def test_self_scope() -> None:
    assert scope_matches("self", "", ME, None)
    assert scope_matches("self", "", ME, ResourceRef("profile", "1", owner_id=ME))
    assert not scope_matches("self", "", ME, ResourceRef("profile", "2", owner_id=OTHER))
    assert not scope_matches("self", "", ME, ResourceRef("settings", "global"))


def test_owned_scope_needs_an_owner() -> None:
    assert scope_matches("owned", "", ME, ResourceRef("ticket", "1", owner_id=ME))
    assert not scope_matches("owned", "", ME, ResourceRef("ticket", "1"))
    assert not scope_matches("owned", "", ME, None)
    assert not scope_matches("owned", "", ME, ResourceRef("ticket", "2", owner_id=OTHER))


def test_service_scope_does_not_cross_services() -> None:
    assert scope_matches("service", "plex-a", ME, ResourceRef("service", "plex-a"))
    assert scope_matches(
        "service", "plex-a", ME, ResourceRef("library", "9", attributes={"service_id": "plex-a"})
    )
    assert not scope_matches("service", "plex-a", ME, ResourceRef("service", "plex-b"))
    assert not scope_matches("service", "", ME, ResourceRef("service", ""))


def test_module_and_plugin_scopes() -> None:
    assert scope_matches("module", "wiki", ME, ResourceRef("page", "1", attributes={"module": "wiki"}))
    assert not scope_matches("module", "wiki", ME, ResourceRef("page", "1", attributes={"module": "news"}))
    assert scope_matches("plugin", "weather", ME, ResourceRef("x", attributes={"plugin_id": "weather"}))
    assert not scope_matches("plugin", "weather", ME, ResourceRef("x", attributes={"plugin_id": "radar"}))
    assert not scope_matches("unknown", "", ME, ResourceRef("x"))


def test_global_scope_matches_everything() -> None:
    assert scope_matches("global", "", ME, None)
    assert scope_matches("global", "", ME, ResourceRef("service", "plex-b"))
