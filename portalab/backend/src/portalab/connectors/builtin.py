"""Connectors shipped with the portal (registered by the app at start; plugins may add more)."""

from portalab.capabilities.connector_sdk import Connector, ConnectorRegistry
from portalab.connectors.arr import RadarrConnector, SonarrConnector
from portalab.connectors.authentik import AuthentikConnector
from portalab.connectors.glances import GlancesConnector
from portalab.connectors.grimmory import GrimmoryConnector
from portalab.connectors.jellyfin import JellyfinConnector
from portalab.connectors.maintainerr import MaintainerrConnector
from portalab.connectors.ollama import OllamaConnector
from portalab.connectors.plex import PlexConnector
from portalab.connectors.romm import RommConnector
from portalab.connectors.seerr import SeerrConnector
from portalab.connectors.tautulli import TautulliConnector
from portalab.connectors.tmdb import TmdbConnector
from portalab.connectors.torrents import DelugeConnector, QBittorrentConnector
from portalab.connectors.unraid import UnraidConnector

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
        AuthentikConnector(),  # 027: the single sign-on — accounts and the groups opening each service
        GlancesConnector(),  # #49: a server's processor, memory, temperatures, disks, containers
        UnraidConnector(),  # #50: an Unraid server's array, disks, containers and updates
        MaintainerrConnector(),  # #57: the library's cleanup — what will be deleted, saving a title
        OllamaConnector(),  # issue 169: language models on the local network — the assistant's
    ]


def register_builtin(registry: ConnectorRegistry) -> None:
    for connector in builtin_connectors():
        if registry.get(connector.key) is None:
            registry.register(connector, owner=OWNER)
