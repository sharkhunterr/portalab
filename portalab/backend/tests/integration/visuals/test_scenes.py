"""028 (US5): a booster scene from a pack — bound at review to every booster (or one), read with its parts,
Portalab's own scene back when its pack is off; a part the scene does not bring keeps Portalab's."""

import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.modules.visuals.store import read_folder
from tests.integration.visuals.test_registry import _service
from tests.unit.visuals.support import FakeInterfaces, zip_of

EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "visual-packs" / "booster-scene"
ADMIN = Principal(user_id=uuid4(), channel="user")
pytestmark = pytest.mark.integration


async def test_a_scene_bound_at_review_dresses_every_booster(database: Database, tmp_path: Path) -> None:
    from portalab.modules.visuals.analysis import analyse

    assert analyse(read_folder(EXAMPLE), interfaces=FakeInterfaces())["summary"]["publishable"]
    service, writer, _ = _service(database, tmp_path)
    shutil.copytree(EXAMPLE, tmp_path / "inbox" / "maree")
    await service.scan(ADMIN)
    import json

    version = json.loads((EXAMPLE / "pack.json").read_text())["version"]
    await service.save_draft(ADMIN, "maree", version, {"bindings": {"maree": "*"}})
    await service.publish(ADMIN, "maree", version)
    assert writer.products == {}  # a scene and its parts are never shop products
    scene = await service.scene_for("booster_classic")
    assert scene is not None and scene["look"] == "maree"
    parts = scene["parts"]
    # the chest: its GPU light and its own stylesheet (the shape), an opening of its own with its time
    assert parts["booster_look"]["kind"] == "glsl" and parts["booster_look"]["css"][0].endswith("chest.css")
    assert parts["backdrop"]["stage"] is True and parts["opening"]["duration"] == 2.6
    assert parts["reveal"]["legendary"]["kind"] == "glsl" and "common" not in parts["reveal"]
    assert set(parts["face"]) == {"common", "rare", "epic", "legendary"}
    assert parts["back"]["common"]["css"][0].endswith("back.css")
    # issue 153: what the shop's tiles read (the sealed pack takes the chest's stylesheet) and what the
    # administrators may make a booster of (its scenes; its parts are never a pack's sold items)
    bindings = (await service.scene_bindings())["bindings"]
    assert bindings["*"]["pack"] == "maree" and bindings["*"]["booster_look"] == "maree"
    assert bindings["*"]["card_back"] == "maree"  # the shop shows a card face down, its back
    options = await service.booster_options()
    assert {(s["pack"], s["look"]) for s in options["scenes"]} == {("maree", "maree")}
    assert "maree" not in {p["id"] for p in options["packs"]}
    # issue 154: the Test step rebuilds the scene from the version's own elements, found by their folder
    detail = await service.detail("maree", version)
    assert {e.get("folder") for e in detail["elements"]} >= {"scene-maree", "look-maree", "back-maree"}
    # a booster bound to no scene of its own takes the default one; unbinding gives Portalab's back
    await service.bind_scene(ADMIN, "*", None)
    assert await service.scene_for("booster_classic") is None
    await service.bind_scene(ADMIN, "booster_abysses", ("maree", "maree"))
    assert await service.scene_for("booster_classic") is None
    assert (await service.scene_for("booster_abysses") or {}).get("look") == "maree"
    # its pack switched off: Portalab's own scene
    await service.set_state(ADMIN, "maree", False)
    assert await service.scene_for("booster_abysses") is None


async def test_a_scene_naming_a_missing_part_is_refused(database: Database, tmp_path: Path) -> None:
    import json

    pack = tmp_path / "bad"
    shutil.copytree(EXAMPLE, pack)
    scene = pack / "elements" / "scene-maree" / "element.json"
    data = json.loads(scene.read_text())
    data["payload"]["parts"]["opening"] = "nowhere"
    scene.write_text(json.dumps(data))
    from portalab.modules.visuals.analysis import analyse

    codes = {i["code"] for i in analyse(read_folder(pack))["items"] if i["level"] == "blocking"}
    assert "scene.part" in codes
    service, _, _ = _service(database, tmp_path / "data")
    imported = await service.upload(
        "bad.zip",
        zip_of({p.relative_to(pack).as_posix(): p.read_bytes() for p in pack.rglob("*") if p.is_file()}),
    )
    assert (await service.detail(imported.pack, imported.version))["outcomes"]["analysis"] == "blocking"


async def test_a_new_version_keeps_the_boosters_scenes(database: Database, tmp_path: Path) -> None:
    """Issue 153: a booster given a pack's scene keeps it when the pack's next version is published."""
    import json

    service, _, _ = _service(database, tmp_path)
    first = tmp_path / "inbox" / "maree"
    shutil.copytree(EXAMPLE, first)
    await service.scan(ADMIN)
    version = json.loads((EXAMPLE / "pack.json").read_text())["version"]
    await service.publish(ADMIN, "maree", version)
    await service.bind_scene(ADMIN, "booster_tide", ("maree", "maree"))
    shutil.rmtree(first)
    second = tmp_path / "inbox" / "maree-next"
    shutil.copytree(EXAMPLE, second)
    manifest = json.loads((second / "pack.json").read_text())
    manifest["version"] = "9.0.0"
    (second / "pack.json").write_text(json.dumps(manifest))
    await service.scan(ADMIN)
    await service.publish(ADMIN, "maree", "9.0.0")
    scene = await service.scene_for("booster_tide")
    assert scene is not None and scene["look"] == "maree"
    assert (await service.scene_bindings())["bindings"]["booster_tide"]["card_back"] == "maree"
