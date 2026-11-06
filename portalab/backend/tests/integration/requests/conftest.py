"""Requests fixtures (issue 363, #378): the media harness (the portal's requests, the library they are checked
against) and an app with the team's request service wired."""

import pytest
from fastapi import FastAPI

from portalab.modules.requests.module import RequestsModule
from tests.integration.media.conftest import MediaHarness, client, clock, media  # noqa: F401


@pytest.fixture
def team(media: MediaHarness) -> RequestsModule:  # noqa: F811
    module = RequestsModule(
        media.database, media.ev.full.identity.capabilities, clock=media.module.clock, sinks=media.sinks
    )
    module.register()
    return module


@pytest.fixture
def app(media: MediaHarness, heads: set[str], team: RequestsModule) -> FastAPI:  # noqa: F811
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
        requests=team,
        static_dir=None,
    )
