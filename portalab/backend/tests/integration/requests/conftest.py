"""Requests fixtures (issue 363): the media harness (the library the requests are checked against) and an app
with the requests module wired."""

import pytest
from fastapi import FastAPI

from portalab.modules.requests.module import RequestsModule
from tests.integration.media.conftest import MediaHarness, client, clock, media  # noqa: F401


@pytest.fixture
def wishes(media: MediaHarness) -> RequestsModule:  # noqa: F811
    module = RequestsModule(
        media.database,
        media.ev.full.identity.capabilities,
        clock=media.module.clock,
        events=media.ev.publisher,
        event_types=media.ev.types,
    )
    module.register()
    return module


@pytest.fixture
def app(media: MediaHarness, heads: set[str], wishes: RequestsModule) -> FastAPI:  # noqa: F811
    from portalab.app.main import create_app

    full = media.ev.full
    return create_app(
        database=full.database,
        migration_heads=heads,
        identity=full.identity,
        authz=full.authz,
        privacy=full.privacy,
        administration=full.administration,
        media=media.module,
        requests=wishes,
        static_dir=None,
    )
