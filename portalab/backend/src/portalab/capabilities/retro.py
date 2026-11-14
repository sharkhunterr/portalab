"""Retro play (issues 419-421): playing a game library's games in the portal's page.

* ``media.retro_source`` — provided by a game library connector (RomM), one per service: a game's ROM and its
  platform, the platform's firmware (BIOS), the emulator's own files (EmulatorJS, as the library serves
  them: the portal relays them, the library is never exposed) and the play sessions sent back to it;
* ``media.game_source`` — provided by Media: which service holds a catalog game, and as which item — once the
  viewer may open it (a household profile's restrictions hold).
"""

from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, runtime_checkable
from uuid import UUID

from portalab.capabilities.media import StreamBody
from portalab.capabilities.registry import CapabilitySpec
from portalab.core.authz_port import Principal

RETRO_SOURCE = "media.retro_source"
GAME_SOURCE = "media.game_source"
FileKind = Literal["rom", "firmware", "emulator"]
SaveKind = Literal["save", "state"]  # 420: a game's own save (its battery memory), a save state


@dataclass(frozen=True, slots=True)
class RetroGame:
    external_id: str
    title: str
    platform: str  # the library's platform slug (« snes », « gba », « psx »…)
    platform_id: str
    file_name: str  # the library's name of the game's file (or folder, for a game of several files)
    size: int | None = None
    multi: bool = False  # several files: the library sends them as one archive
    present: bool = True  # its file is on the library's disk


@dataclass(frozen=True, slots=True)
class RetroFirmware:
    id: str
    file_name: str
    verified: bool = False


@runtime_checkable
class RetroSource(Protocol):
    async def game(self, external_id: str) -> RetroGame | None: ...

    async def firmware(self, platform_id: str) -> Sequence[RetroFirmware]: ...

    def open(
        self, kind: FileKind, ref: str, name: str, range_header: str | None = None
    ) -> AbstractAsyncContextManager[StreamBody]:
        """A file relayed as the library sends it (a 206 for a range): ``rom`` (``ref`` the game, ``name``
        its file), ``firmware`` (``ref`` its id), ``emulator`` (``name`` a path under its data folder)."""
        ...

    async def record_session(
        self, external_id: str, started_at: datetime, ended_at: datetime, duration_ms: int
    ) -> None:
        """A play session, told to the library (which keeps the account's play time) — as the portal's own
        device, whose sessions the library's history then leaves out (the portal counted them already)."""
        ...

    async def put_file(
        self,
        kind: SaveKind,
        external_id: str,
        core: str,
        file_name: str,
        data: bytes,
        screenshot: bytes | None,
        labels: Sequence[str],
        remote_id: str | None = None,
    ) -> str:
        """420: a member's save or state copied to the library (``remote_id``: the copy to replace, gone
        or not), labelled with who it is (the library's account is shared); its id there."""
        ...

    async def delete_file(self, kind: SaveKind, remote_id: str) -> None:
        """420: a copy removed from the library (gone already: nothing to do)."""
        ...


@dataclass(frozen=True, slots=True)
class GameSource:
    object_id: UUID
    title: str
    service_id: UUID
    external_id: str


@runtime_checkable
class GameSourceLocator(Protocol):
    async def sources(
        self, object_id: UUID, viewer: Principal, services: Sequence[str]
    ) -> Sequence[GameSource]:
        """The items of a catalog game the viewer may open, among the given services (the most recently seen
        first; empty: no such game there). Refuses a title a household profile's restrictions keep from it,
        and a profile whose screen time of the day is spent."""
        ...

    async def screen(self, viewer: Principal) -> tuple[int, int] | None:
        """``(minutes used today, minutes allowed a day)`` for a profile given a screen time, or ``None``."""
        ...


SPECS: tuple[CapabilitySpec, ...] = (
    CapabilitySpec(
        name=RETRO_SOURCE,
        version="1.0",
        protocol=RetroSource,
        multi_provider=True,
        description="A game library's ROMs, firmware, emulator files and play sessions (retro play).",
    ),
    CapabilitySpec(
        name=GAME_SOURCE,
        version="1.0",
        protocol=GameSourceLocator,
        multi_provider=False,
        description="Which service holds a catalog game, once the viewer may open it (owned by media).",
    ),
)
