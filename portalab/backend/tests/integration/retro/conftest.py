"""Retro integration fixtures (issue 419): the media harness, a fake game library and the retro module.

The fake answers as a connector's provider does through the connectors' guard: its calls give results
(``Available``, ``Unavailable``), its streams the bodies themselves."""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI

from portalab.capabilities.media import StreamBody
from portalab.capabilities.results import Available, CapabilityResult, Unavailable
from portalab.capabilities.retro import RETRO_SOURCE, FileKind, RetroFirmware, RetroGame, SaveKind
from portalab.core.time import FixedClock
from portalab.modules.retro.module import RetroModule
from tests.integration.media.conftest import MediaHarness, client, clock, media  # noqa: F401 — fixtures


@dataclass
class FakeRetro:
    games: dict[str, RetroGame] = field(default_factory=dict)
    firmwares: dict[str, list[RetroFirmware]] = field(default_factory=dict)
    opened: list[tuple[str, str, str, str | None]] = field(default_factory=list)
    sessions: list[tuple[str, int]] = field(default_factory=list)
    refuse_sessions: bool = False
    copies: list[dict[str, Any]] = field(default_factory=list)  # 420: the saves and states copied
    deleted: list[tuple[str, str]] = field(default_factory=list)
    refuse_copies: bool = False

    async def game(self, external_id: str) -> CapabilityResult[RetroGame | None]:
        return Available(self.games.get(external_id), as_of=datetime.now(UTC))

    async def firmware(self, platform_id: str) -> CapabilityResult[Sequence[RetroFirmware]]:
        return Available(self.firmwares.get(platform_id, []), as_of=datetime.now(UTC))

    @asynccontextmanager
    async def open(
        self, kind: FileKind, ref: str, name: str, range_header: str | None = None
    ) -> AsyncIterator[StreamBody]:
        self.opened.append((kind, ref, name, range_header))
        data = f"{kind}:{name}".encode()

        async def chunks() -> AsyncIterator[bytes]:
            yield data

        yield StreamBody(
            status=206 if range_header else 200,
            content_type="application/octet-stream",
            length=len(data),
            chunks=chunks(),
            content_range=f"bytes 0-{len(data) - 1}/{len(data)}" if range_header else None,
        )

    async def record_session(
        self, external_id: str, started_at: datetime, ended_at: datetime, duration_ms: int
    ) -> CapabilityResult[None]:
        if self.refuse_sessions:
            return Unavailable(detail="down")
        self.sessions.append((external_id, duration_ms))
        return Available(None, as_of=datetime.now(UTC))

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
    ) -> CapabilityResult[str]:
        if self.refuse_copies:
            return Unavailable(detail="down")
        self.copies.append(
            {
                "kind": kind,
                "rom": external_id,
                "core": core,
                "name": file_name,
                "data": data,
                "picture": screenshot,
                "labels": list(labels),
                "replaces": remote_id,
            }
        )
        return Available(remote_id or str(100 + len(self.copies)), as_of=datetime.now(UTC))

    async def delete_file(self, kind: SaveKind, remote_id: str) -> CapabilityResult[None]:
        self.deleted.append((kind, remote_id))
        return Available(None, as_of=datetime.now(UTC))


@pytest.fixture
def retro(media: MediaHarness) -> FakeRetro:  # noqa: F811
    fake = FakeRetro(
        games={
            "r1": RetroGame("r1", "Super Metroid", "snes", "3", "Super Metroid (E).sfc", size=9),
            "r2": RetroGame("r2", "Pong", "magnavox", "8", "pong.bin"),  # no emulator here
        },
        firmwares={"3": [RetroFirmware("5", "bios.bin", verified=True)]},
    )
    media.provide(RETRO_SOURCE, media.service(1), fake)
    return fake


@pytest.fixture
def retro_module(media: MediaHarness, clock: FixedClock) -> RetroModule:  # noqa: F811
    module = RetroModule(
        media.database, media.ev.full.identity.capabilities, clock=clock, events=media.ev.publisher
    )
    module.register()
    return module


@pytest.fixture
def app(media: MediaHarness, retro_module: RetroModule, heads: set[str]) -> FastAPI:  # noqa: F811
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
        retro=retro_module,
        static_dir=None,
    )
