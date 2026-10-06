"""Connectors shipped with the portal (registered by the app at start; plugins may add more)."""

from portalab.capabilities.connector_sdk import Connector, ConnectorRegistry
from portalab.connectors.arr import RadarrConnector, SonarrConnector
from portalab.connectors.grimmory import GrimmoryConnector
from portalab.connectors.jellyfin import JellyfinConnector
from portalab.connectors.plex import PlexConnector
from portalab.connectors.romm import RommConnector
from portalab.connectors.seerr import SeerrConnector
from portalab.connectors.tautulli import TautulliConnector
from portalab.connectors.tmdb import TmdbConnector
from portalab.connectors.torrents import DelugeConnector, QBittorrentConnector

OWNER = "core:connectors"


def builtin_connectors() -> list[Connector]:
    return [
        JellyfinConnector(),
        PlexConnector(),
        SeerrConnector(),
        RadarrConnector(),
        SonarrConnector(),
        RommConnector(),
        TautulliConnector(),
        GrimmoryConnector(),
        TmdbConnector(),
        QBittorrentConnector(),
        DelugeConnector(),
    ]


def register_builtin(registry: ConnectorRegistry) -> None:
    for connector in builtin_connectors():
        if registry.get(connector.key) is None:
            registry.register(connector, owner=OWNER)
