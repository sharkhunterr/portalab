"""Test-only declarations (owner ``test:admin``), removed after each test."""

from collections.abc import Iterator

import pytest

from portalab.core.config_declaration import default_catalog

OWNER = "test:admin"


@pytest.fixture
def test_settings() -> Iterator[None]:
    default_catalog.declare(
        scope="user",
        key="demo.theme",
        schema=str,
        default="auto",
        owner=OWNER,
        user_overridable=True,
        description="Theme",
    )
    default_catalog.declare(
        scope="global",
        key="demo.pageSize",
        schema=int,
        default=20,
        owner=OWNER,
        user_overridable=True,
        description="Rows per page",
    )
    default_catalog.declare(
        scope="global",
        key="demo.apiToken",
        schema=str,
        default=None,
        sensitive=True,
        owner=OWNER,
        description="Secret token",
    )
    yield
    default_catalog.unregister(OWNER)
