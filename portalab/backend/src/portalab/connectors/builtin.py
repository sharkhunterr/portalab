"""Connectors shipped with the portal (registered by the app at start; plugins may add more)."""

from portalab.capabilities.connector_sdk import Connector, ConnectorRegistry
from portalab.connectors.arr import RadarrConnector, SonarrConnector
from portalab.connectors.jellyfin import JellyfinConnector
from portalab.connectors.plex import PlexConnector
from portalab.connectors.romm import RommConnector
from portalab.connectors.seerr import SeerrConnector

OWNER = "core:connectors"


def builtin_connectors() -> list[Connector]:
    return [
        JellyfinConnector(),
        PlexConnector(),
        SeerrConnector(),
        RadarrConnector(),
        SonarrConnector(),
        RommConnector(),
    ]


def register_builtin(registry: ConnectorRegistry) -> None:
    for connector in builtin_connectors():
        if registry.get(connector.key) is None:
            registry.register(connector, owner=OWNER)
