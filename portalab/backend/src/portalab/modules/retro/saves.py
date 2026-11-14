"""Saves and save states (issue 420): a member's progress in a game, kept in the portal per member and per
household profile — the library's account is shared by everyone, so the portal tells whose is whose.

* a game's own save (``sram``, its battery memory): one per game, written by the page each time the emulator
  writes it (every minute while playing, and when the game is left), loaded when the game starts;
* save states, in slots: 1 to :data:`SLOTS` chosen by the member, 0 where the game was left (« Continue »
  starts from the latest one), each with a picture of the screen;
* each copied to the library (RomM's saves and states, labelled « Portalab » and with the member's name) once
  written — retried by the sweep when the library did not answer; a state deleted here is deleted there.

Only the sitting's player reads or writes them, while the sitting is open (as its files).
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import undefer

from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.retro import SaveKind
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import BadRequest, NotFound
from portalab.core.logging import get_logger
from portalab.core.time import Clock, utc_now
from portalab.modules.retro.models import GameSave, Sitting
from portalab.modules.retro.service import TIMEOUT_S, RetroService, _value

SLOTS = 5  # the member's own slots (slot 0: where the game was left)
MAX_BYTES = 9 * 1024 * 1024  # under the portal's default request cap (an emulator's whole memory)
MAX_PICTURE = 1024 * 1024
PICTURES = {b"\x89PNG\r\n\x1a\n": "image/png", b"\xff\xd8\xff": "image/jpeg", b"RIFF": "image/webp"}
LABEL = "Portalab"
KINDS: dict[str, SaveKind] = {"sram": "save", "state": "state"}
log = get_logger("portalab.retro")


class SaveNotFound(NotFound):
    default_code = "retro.save_not_found"
    default_title = "No such save"


class SaveRefused(BadRequest):
    default_code = "retro.save_refused"
    default_title = "This save cannot be kept"


@dataclass(frozen=True, slots=True)
class StateInfo:
    slot: int
    size: int
    updated_at: datetime
    has_picture: bool


@dataclass(frozen=True, slots=True)
class Progress:
    sram_at: datetime | None
    states: list[StateInfo]

    @property
    def latest(self) -> StateInfo | None:
        return max(self.states, key=lambda s: s.updated_at, default=None)


def picture_type(data: bytes) -> str | None:
    for magic, kind in PICTURES.items():
        if data.startswith(magic) and (kind != "image/webp" or data[8:12] == b"WEBP"):
            return kind
    return None


def _slot(kind: str, slot: int) -> int:
    if kind == "sram":
        return 0
    if not 0 <= slot <= SLOTS:
        raise SaveRefused(f"A slot is from 0 to {SLOTS}.")
    return slot


class SaveService:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        retro: RetroService,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.retro = retro
        self.clock = clock

    async def progress(self, user: UUID, service: UUID, external_id: str) -> Progress:
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(
                        GameSave.kind,
                        GameSave.slot,
                        GameSave.size,
                        GameSave.updated_at,
                        GameSave.screenshot.is_not(None).label("pictured"),
                    ).where(
                        GameSave.user_id == user,
                        GameSave.service_id == service,
                        GameSave.external_id == external_id,
                    )
                )
            ).all()
        sram = next((r.updated_at for r in rows if r.kind == "sram"), None)
        states = sorted(
            (StateInfo(r.slot, r.size, r.updated_at, bool(r.pictured)) for r in rows if r.kind == "state"),
            key=lambda s: s.slot,
        )
        return Progress(sram_at=sram, states=states)

    async def of_sitting(self, viewer: Principal, sitting: UUID) -> tuple[Sitting, Progress]:
        row = await self.retro._sitting(viewer, sitting)
        return row, await self.progress(row.user_id, row.service_id, row.external_id)

    async def read(self, viewer: Principal, sitting: UUID, kind: str, slot: int) -> bytes:
        row = await self.retro._sitting(viewer, sitting)
        found = await self._find(row, kind, _slot(kind, slot), "data")
        return found.data

    async def picture(self, viewer: Principal, sitting: UUID, slot: int) -> tuple[bytes, str]:
        row = await self.retro._sitting(viewer, sitting)
        found = await self._find(row, "state", _slot("state", slot), "screenshot")
        kind = picture_type(found.screenshot or b"")
        if found.screenshot is None or kind is None:
            raise SaveNotFound("No picture for this slot.")
        return found.screenshot, kind

    async def _find(self, row: Sitting, kind: str, slot: int, column: str) -> GameSave:
        async with self.database.session() as session:
            found = await session.scalar(
                select(GameSave)
                .options(undefer(getattr(GameSave, column)))
                .where(*self._key(row, kind, slot))
            )
        if found is None:
            raise SaveNotFound("Nothing saved here.")
        return found

    def _key(self, row: Sitting, kind: str, slot: int) -> tuple[Any, ...]:
        return (
            GameSave.user_id == row.user_id,
            GameSave.service_id == row.service_id,
            GameSave.external_id == row.external_id,
            GameSave.kind == kind,
            GameSave.slot == slot,
        )

    async def write(self, viewer: Principal, sitting: UUID, kind: str, slot: int, data: bytes) -> StateInfo:
        """The emulator's save or state, kept for the sitting's player (replacing the slot's), then copied."""
        if kind not in KINDS:
            raise SaveNotFound("No such kind of save.")
        if not data or len(data) > MAX_BYTES:
            raise SaveRefused("This save is empty or too large.")
        row = await self.retro._sitting(viewer, sitting)
        slot = _slot(kind, slot)
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                insert(GameSave)
                .values(
                    user_id=row.user_id,
                    object_id=row.object_id,
                    service_id=row.service_id,
                    external_id=row.external_id,
                    kind=kind,
                    slot=slot,
                    core=row.core,
                    data=data,
                    size=len(data),
                    screenshot=None,
                    updated_at=now,
                    synced_at=None,
                )
                .on_conflict_do_update(
                    constraint="uq_saves_slot",
                    set_={
                        "data": data,
                        "size": len(data),
                        "core": row.core,
                        "screenshot": None,
                        "updated_at": now,
                        "synced_at": None,
                    },
                )
            )
        await self.sync_one(row.user_id, row.service_id, row.external_id, kind, slot)
        return StateInfo(slot, len(data), now, False)

    async def write_picture(self, viewer: Principal, sitting: UUID, slot: int, data: bytes) -> None:
        """The screen when a state was saved (a PNG, JPEG or WebP picture)."""
        if len(data) > MAX_PICTURE or picture_type(data) is None:
            raise SaveRefused("This picture is not one the portal keeps.")
        row = await self.retro._sitting(viewer, sitting)
        async with self.database.unit_of_work() as uow:
            found = await uow.session.scalar(
                select(GameSave).where(*self._key(row, "state", _slot("state", slot))).with_for_update()
            )
            if found is None:
                raise SaveNotFound("Nothing saved here.")
            found.screenshot = data
            found.synced_at = None
        await self.sync_one(row.user_id, row.service_id, row.external_id, "state", slot)

    async def remove(self, viewer: Principal, sitting: UUID, slot: int) -> None:
        row = await self.retro._sitting(viewer, sitting)
        async with self.database.unit_of_work() as uow:
            gone = (
                await uow.session.execute(
                    delete(GameSave)
                    .where(*self._key(row, "state", _slot("state", slot)))
                    .returning(GameSave.remote_id)
                )
            ).scalar_one_or_none()
        library = self.retro._libraries().get(str(row.service_id))
        if gone and library is not None:
            try:
                _value(await asyncio.wait_for(library[0].delete_file("state", gone), timeout=TIMEOUT_S))
            except Exception:
                log.warning("retro state not deleted from the library", extra={"remote": gone})

    # --- copies in the library --------------------------------------------------------------------------
    async def sync_one(self, user: UUID, service: UUID, external_id: str, kind: str, slot: int) -> bool:
        async with self.database.session() as session:
            found = await session.scalar(
                select(GameSave)
                .options(undefer(GameSave.data), undefer(GameSave.screenshot))
                .where(
                    GameSave.user_id == user,
                    GameSave.service_id == service,
                    GameSave.external_id == external_id,
                    GameSave.kind == kind,
                    GameSave.slot == slot,
                )
            )
        return await self._copy(found) if found is not None and found.synced_at is None else False

    async def _copy(self, save: GameSave) -> bool:
        library = self.retro._libraries().get(str(save.service_id))
        if library is None:
            return False
        name = await self._name(save.user_id)
        extension = "srm" if save.kind == "sram" else f"slot{save.slot}.state"
        try:
            remote = _value(
                await asyncio.wait_for(
                    library[0].put_file(
                        KINDS[save.kind],
                        save.external_id,
                        save.core,
                        f"portalab-{save.user_id.hex}-{save.external_id}.{extension}",
                        save.data,
                        save.screenshot
                        if save.screenshot and picture_type(save.screenshot) == "image/png"
                        else None,
                        [LABEL, *([name] if name else [])],
                        save.remote_id,
                    ),
                    timeout=TIMEOUT_S,
                )
            )
        except Exception:
            log.warning("retro save not copied to the library", extra={"save": str(save.id)})
            return False
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(GameSave, save.id, with_for_update=True)
            if row is not None:
                row.remote_id = str(remote)[:64]
                if row.updated_at == save.updated_at and row.synced_at is None:
                    row.synced_at = utc_now(self.clock)  # written again meanwhile: copied again
        return True

    async def _name(self, user: UUID) -> str | None:
        providers = self.capabilities.system_providers(DIRECTORY)
        if not providers:
            return None
        try:
            summary = await providers[0].provider.get_user_summary(user)
        except Exception:
            return None
        return summary.display_name if summary is not None else None

    async def sync(self, limit: int = 50) -> int:
        """The saves the library was not given yet (it did not answer), copied now."""
        async with self.database.session() as session:
            rows = list(
                await session.scalars(
                    select(GameSave)
                    .options(undefer(GameSave.data), undefer(GameSave.screenshot))
                    .where(GameSave.synced_at.is_(None))
                    .order_by(GameSave.updated_at)
                    .limit(limit)
                )
            )
        copied = 0
        for row in rows:
            copied += await self._copy(row)
        return copied
