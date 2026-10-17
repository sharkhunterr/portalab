"""028 (T095): a malformed archive stores nothing — no pack, no version, no file kept — whether it is uploaded
from the administration or offered by GitHub; and GitHub is never followed off its own host. The archives
are built here, at test time (never committed): a path climbing out of the pack, an absolute path, a link, a
control character in a name, a file over the size allowed, a kind of file a pack may not hold."""

import io
import zipfile
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select

from portalab.capabilities.catalog import new_registry
from portalab.capabilities.visuals import CATALOG_WRITER, INTERFACE_REGISTRY
from portalab.core.db import Database
from portalab.modules.visuals.github import GitHub
from portalab.modules.visuals.models import Pack, PackVersion
from portalab.modules.visuals.service import VisualPackError, VisualPacks
from portalab.modules.visuals.store import MAX_FILE_BYTES
from tests.unit.visuals.support import FakeInterfaces, FakeWriter, tiny_pack, zip_of


def _service(database: Database, root: Path, github: GitHub | None = None) -> VisualPacks:
    registry = new_registry()
    registry.provide(CATALOG_WRITER, FakeWriter(), instance_ref="test", owner="test")
    registry.provide(INTERFACE_REGISTRY, FakeInterfaces(), instance_ref="test", owner="test")
    return VisualPacks(database, root, registry, github=github)


def _with_link() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in tiny_pack().items():
            archive.writestr(name, data)
        link = zipfile.ZipInfo("elements/frame/linked.css")
        link.external_attr = 0o120777 << 16  # a symbolic link
        archive.writestr(link, "../../../outside")
    return buffer.getvalue()


MALFORMED = {
    "climbing": lambda: zip_of({**tiny_pack(), "../outside.css": "x"}),
    "absolute": lambda: zip_of({**tiny_pack(), "/outside.css": "x"}),
    "link": _with_link,
    "control character": lambda: zip_of({**tiny_pack(), "elements/frame/a\x01b.css": "x"}),
    "oversize": lambda: zip_of({**tiny_pack(), "elements/frame/big.css": b"0" * (MAX_FILE_BYTES + 1)}),
    "forbidden kind": lambda: zip_of({**tiny_pack(), "elements/frame/tool.exe": b"MZ"}),
    "not an archive": lambda: b"PK\x03\x04 not a zip",
}


def _files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file()]


async def _nothing_kept(database: Database, root: Path) -> None:
    async with database.session() as session:
        assert await session.scalar(select(func.count()).select_from(Pack)) == 0
        assert await session.scalar(select(func.count()).select_from(PackVersion)) == 0
    assert _files(root) == []


@pytest.mark.parametrize("kind", sorted(MALFORMED))
async def test_a_malformed_upload_stores_nothing(database: Database, tmp_path: Path, kind: str) -> None:
    service = _service(database, tmp_path)
    with pytest.raises(VisualPackError):
        await service.upload("pack.zip", MALFORMED[kind]())
    await _nothing_kept(database, tmp_path)


@pytest.mark.parametrize("kind", ["climbing", "link", "oversize"])
async def test_a_malformed_github_archive_stores_nothing(
    database: Database, tmp_path: Path, kind: str
) -> None:
    archive = MALFORMED[kind]()

    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/releases/latest"):
            return httpx.Response(200, json={"tag_name": "v1.0.0"})
        return httpx.Response(200, content=archive)

    github = GitHub(httpx.AsyncClient(transport=httpx.MockTransport(answer)))
    service = _service(database, tmp_path, github)
    with pytest.raises(VisualPackError):
        await service.from_github("https://github.com/acme/looks")
    await _nothing_kept(database, tmp_path)


async def test_github_is_never_followed_off_its_host(database: Database, tmp_path: Path) -> None:
    asked: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        asked.append(request.url.host)
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data"})

    github = GitHub(httpx.AsyncClient(transport=httpx.MockTransport(answer)))
    service = _service(database, tmp_path, github)
    with pytest.raises(VisualPackError):
        await service.from_github("https://github.com/acme/looks")
    assert "169.254.169.254" not in asked
    await _nothing_kept(database, tmp_path)
