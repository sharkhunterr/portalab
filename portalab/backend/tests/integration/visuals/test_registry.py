"""028: the registry of visual packs in PostgreSQL — import, the workflow's steps, publication with the look
claims, switching off and on, rollback, archive / removal / purge, and what members are served."""

import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from portalab.capabilities.catalog import new_registry
from portalab.capabilities.visuals import CATALOG_WRITER, INTERFACE_REGISTRY, live_looks
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound
from portalab.core.live import LiveEvent
from portalab.modules.visuals.github import GitHub
from portalab.modules.visuals.models import LookClaim
from portalab.modules.visuals.service import VisualPackError, VisualPacks
from tests.unit.visuals.support import FakeInterfaces, FakeWriter, tiny_pack, zip_of

EXAMPLES = Path(__file__).resolve().parents[4] / "examples" / "visual-packs"
ADMIN = Principal(user_id=uuid4(), channel="user")


@pytest.fixture(autouse=True)
def _no_live_looks() -> Iterator[None]:
    yield
    live_looks.replace({})


def _service(database: Database, root: Path) -> tuple[VisualPacks, FakeWriter, FakeInterfaces]:
    registry = new_registry()
    writer, interfaces = FakeWriter(), FakeInterfaces()
    registry.provide(CATALOG_WRITER, writer, instance_ref="test", owner="test")
    registry.provide(INTERFACE_REGISTRY, interfaces, instance_ref="test", owner="test")
    return VisualPacks(database, root, registry), writer, interfaces


async def test_the_workflow_from_the_inbox_to_the_shop(database: Database, tmp_path: Path) -> None:
    service, writer, interfaces = _service(database, tmp_path)
    shutil.copytree(EXAMPLES / "nordlys", tmp_path / "inbox" / "nordlys")
    found = (await service.scan(ADMIN))["found"]
    assert found[0]["new"] and found[0]["pack"] == "nordlys"
    assert (await service.scan())["found"][0]["new"] is False  # read again: nothing new
    detail = await service.detail("nordlys", "1.0.0")
    assert detail["step"] == "analysed" and detail["outcomes"]["security"] == "done"
    await service.record_measures(ADMIN, "nordlys", "1.0.0", [{"element": "frame_nordlys", "fps": 58}])
    assert (await service.detail("nordlys", "1.0.0"))["step"] == "tested"
    draft = {"economy": {"levelup_nordlys": {"price": 1800, "level": 30}}, "confirmations": {"scripts": True}}
    assert (await service.save_draft(ADMIN, "nordlys", "1.0.0", draft))["step"] == "reviewed"
    # a pack running scripts needs it said out loud
    with pytest.raises(VisualPackError):
        await service.publish(ADMIN, "nordlys", "1.0.0")
    result = await service.publish(ADMIN, "nordlys", "1.0.0", confirmations={"scripts": True})
    assert result["products"]["levelup_nordlys"] == "created"
    product = writer.products["levelup_nordlys"]
    assert (product["price"], product["level"], product["rarity"]) == (1800, 30, "legendary")
    assert product["payload"] == {"animation": "nordlys"}
    assert interfaces.rows["nordlys"] == {"source": "visuals:nordlys", "enabled": True}
    listing = await service.listing()
    assert listing[0]["state"] == "enabled" and listing[0]["current"] == "1.0.0"
    # the open vocabulary and what members load
    active = await service.active()
    assert "nordlys" in live_looks.known("level_up") and "fjord" in live_looks.known("ambient")
    level_up = next(e for e in active["elements"] if e.get("product") == "levelup_nordlys")
    assert level_up["file"].startswith("/api/v1/visuals/files/nordlys/") and level_up["reveal"] == 2.4
    sha, name = level_up["file"].split("/nordlys/", 1)[1].split("/", 1)
    assert await service.served("nordlys", sha, name, manager=False) is not None
    async with database.session() as session:
        topics = [e.topic for e in (await session.execute(select(LiveEvent))).scalars()]
    assert "visuals.changed" in topics


async def test_switch_off_and_on_roll_back_and_withdraw_what_a_version_drops(
    database: Database, tmp_path: Path
) -> None:
    service, writer, interfaces = _service(database, tmp_path)
    folder = tmp_path / "inbox" / "nordlys"
    shutil.copytree(EXAMPLES / "nordlys", folder)
    await service.scan()
    economy = {"levelup_nordlys": {"price": 1800}}
    await service.publish(ADMIN, "nordlys", "1.0.0", economy, {"scripts": True})
    level_up = next(e for e in (await service.active())["elements"] if e.get("product") == "levelup_nordlys")
    sha, name = level_up["file"].split("/nordlys/", 1)[1].split("/", 1)
    # switched off: products off sale, files no longer served, looks fall back
    await service.set_state(ADMIN, "nordlys", False)
    assert "levelup_nordlys" in writer.withdrawn and not interfaces.rows["nordlys"]["enabled"]
    assert await service.served("nordlys", sha, name, manager=False) is None
    assert await service.served("nordlys", sha, name, manager=True) is not None  # the Test step still sees it
    await service.refresh(force=True)
    assert "nordlys" not in live_looks.known("level_up") and (await service.active())["elements"] == []
    await service.set_state(ADMIN, "nordlys", True)
    assert writer.products["levelup_nordlys"]["price"] == 1800  # the economy decided is kept
    # a new version without the badge: the badge leaves the shop; rolling back brings it back
    meta = json.loads((folder / "pack.json").read_text())
    (folder / "pack.json").write_text(json.dumps({**meta, "version": "1.1.0"}))
    shutil.rmtree(folder / "elements" / "badge-aurora")
    await service.scan()
    await service.publish(ADMIN, "nordlys", "1.1.0", {}, {"scripts": True})
    assert "badge_nordlys" in writer.withdrawn
    assert (await service.detail("nordlys", "1.0.0"))["step"] == "superseded"
    await service.rollback(ADMIN, "nordlys", "1.0.0")
    assert (await service.listing())[0]["current"] == "1.0.0"
    assert "badge_nordlys" not in writer.withdrawn
    assert writer.products["levelup_nordlys"]["price"] == 1800


async def test_a_published_version_is_never_changed_in_place_and_looks_are_never_shared(
    database: Database, tmp_path: Path
) -> None:
    service, _, _ = _service(database, tmp_path)
    first = await service.upload("tiny.zip", zip_of(tiny_pack()))
    await service.publish(ADMIN, first.pack, first.version)
    changed = tiny_pack()
    changed["elements/frame/f.css"] = '.avatar-frame[data-frame="tiny"] { color: blue; }'
    with pytest.raises(Conflict):
        await service.upload("tiny.zip", zip_of(changed))
    # another pack taking the same look is blocked at its analysis, and cannot be published
    imported = await service.upload("other.zip", zip_of(tiny_pack(pack="other")))
    detail = await service.detail(imported.pack, imported.version)
    assert {"look.taken", "product.taken"} <= {i["code"] for i in detail["report"]["items"]}
    assert detail["outcomes"]["security"] == "blocking"
    with pytest.raises(VisualPackError):
        await service.publish(ADMIN, "other", "1.0.0")


async def test_a_look_is_replaced_only_by_an_explicit_decision_and_given_back(
    database: Database, tmp_path: Path
) -> None:
    service, _, _ = _service(database, tmp_path)
    await service.upload("tiny.zip", zip_of(tiny_pack()))
    await service.publish(ADMIN, "tiny", "1.0.0")
    other = tiny_pack(pack="other", replaces=True, product="frame_other_tiny")
    await service.upload("other.zip", zip_of(other))
    with pytest.raises(Conflict):
        await service.publish(ADMIN, "other", "1.0.0")
    await service.publish(ADMIN, "other", "1.0.0", confirmations={"replaces": ["avatar_frame:tiny"]})
    async with database.session() as session:
        claim = await session.get(LookClaim, ("avatar_frame", "tiny"))
        assert claim is not None and (claim.pack_id, claim.replaced_from) == ("other", "tiny")
    await service.set_state(ADMIN, "other", False)
    async with database.session() as session:
        claim = await session.get(LookClaim, ("avatar_frame", "tiny"))
        assert claim is not None and claim.pack_id == "tiny"  # given back to the pack it had taken it from


async def test_refuse_purge_archive_and_remove(database: Database, tmp_path: Path) -> None:
    service, writer, _ = _service(database, tmp_path)
    await service.upload("tiny.zip", zip_of(tiny_pack()))
    await service.upload("tiny.zip", zip_of(tiny_pack(version="1.1.0")))
    await service.refuse(ADMIN, "tiny", "1.1.0", "not now")
    assert (await service.detail("tiny", "1.1.0"))["step"] == "refused"
    await service.purge(ADMIN, "tiny", "1.1.0")
    await service.publish(ADMIN, "tiny", "1.0.0")
    with pytest.raises(Conflict):
        await service.refuse(ADMIN, "tiny", "1.0.0")
    with pytest.raises(Conflict):
        await service.purge(ADMIN, "tiny", "1.0.0")
    # removed while a member owns its frame: archived, files kept, enabled again at will
    writer.owned["frame_tiny"] = 1
    assert await service.remove(ADMIN, "tiny") == {"outcome": "archived", "owners": 1}
    assert "frame_tiny" in writer.withdrawn
    assert (await service.listing())[0]["state"] == "archived"
    await service.set_state(ADMIN, "tiny", True)
    assert (await service.listing())[0]["state"] == "enabled"
    # nobody owns anything: removed for good
    writer.owned.clear()
    assert await service.remove(ADMIN, "tiny") == {"outcome": "removed", "owners": 0}
    assert writer.retired == ["frame_tiny"] and await service.listing() == []
    assert not (tmp_path / "store" / "tiny").exists()
    with pytest.raises(NotFound):
        await service.detail("tiny", "1.0.0")


async def test_portalab_s_own_ids_are_reserved(database: Database, tmp_path: Path) -> None:
    service, _, _ = _service(database, tmp_path)
    with pytest.raises(Conflict):
        await service.upload("x.zip", zip_of(tiny_pack(pack="portalab-socle")))


async def test_a_pack_from_github_offers_its_updates(database: Database, tmp_path: Path) -> None:
    offered = {"version": "1.0.0"}

    def answer(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/releases/latest"):
            return httpx.Response(200, json={"tag_name": f"v{offered['version']}"})
        if "raw.githubusercontent.com" in url:
            return httpx.Response(200, content=tiny_pack(offered["version"])["pack.json"])
        if "codeload.github.com" in url:
            return httpx.Response(200, content=zip_of(tiny_pack(offered["version"]), prefix="looks-1/"))
        return httpx.Response(404)

    service, _, _ = _service(database, tmp_path)
    service.github = GitHub(httpx.AsyncClient(transport=httpx.MockTransport(answer)))
    imported = await service.from_github("https://github.com/acme/looks")
    assert (imported.pack, imported.version) == ("tiny", "1.0.0")
    assert (await service.check_updates())[0]["update"] is False
    offered["version"] = "1.1.0"
    update: dict[str, Any] = (await service.check_updates())[0]
    assert update["update"] is True and update["offered"] == "1.1.0"
    assert (await service.listing())[0]["update"] is True


async def test_the_proof_of_concept_registry_is_imported_once(database: Database, tmp_path: Path) -> None:
    service, writer, _ = _service(database, tmp_path)
    from portalab.modules.visuals.store import Files

    files = Files({k: v.encode() if isinstance(v, str) else v for k, v in tiny_pack().items()})
    folder = service.store.keep("tiny", files)
    state = {
        "packs": {
            "tiny": {
                "current": "1.0.0",
                "enabled": True,
                "source": {"kind": "upload", "path": "tiny.zip"},
                "versions": {
                    "1.0.0": {
                        "folder": str(folder.relative_to(tmp_path)),
                        "status": "approved",
                        "decision": {"economy": {"frame_tiny": {"price": 777}}},
                    }
                },
            }
        }
    }
    service.store.state_file.write_text(json.dumps(state))
    assert await service.import_poc_state(ADMIN) == 1
    assert writer.products["frame_tiny"]["price"] == 777
    assert not service.store.state_file.exists() and (tmp_path / "state.json.migrated").exists()
