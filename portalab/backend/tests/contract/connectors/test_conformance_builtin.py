"""The connector ConformanceKit, run against every connector shipped with the portal (fake HTTP servers)."""

from portalab.capabilities.connector_sdk import Connector, ServiceHandle
from portalab.connectors.arr import RadarrConnector, SonarrConnector
from portalab.connectors.conformance import ConformanceKit, Scenario
from portalab.connectors.grimmory import GrimmoryConnector
from portalab.connectors.http_base import HttpConnector
from portalab.connectors.jellyfin import JellyfinConnector
from portalab.connectors.plex import PlexConnector
from portalab.connectors.romm import RommConnector
from portalab.connectors.seerr import SeerrConnector
from portalab.connectors.tautulli import TautulliConnector
from portalab.connectors.tmdb import TmdbConnector
from tests.contract.connectors.builtin_fixtures import handle_for


class _Kit(ConformanceKit):
    limit_seconds = 0.5
    connector_class: type[HttpConnector]

    def make_connector(self) -> Connector:
        connector: Connector = self.connector_class()
        return connector

    def make_handle(self, scenario: Scenario) -> ServiceHandle:
        return handle_for(self.connector_class.key, scenario)


class TestJellyfin(_Kit):
    connector_class = JellyfinConnector


class TestPlex(_Kit):
    connector_class = PlexConnector


class TestRadarr(_Kit):
    connector_class = RadarrConnector


class TestSonarr(_Kit):
    connector_class = SonarrConnector


class TestSeerr(_Kit):
    connector_class = SeerrConnector


class TestRomm(_Kit):
    connector_class = RommConnector


class TestTautulli(_Kit):
    connector_class = TautulliConnector


class TestGrimmory(_Kit):
    connector_class = GrimmoryConnector


class TestTmdb(_Kit):
    connector_class = TmdbConnector
