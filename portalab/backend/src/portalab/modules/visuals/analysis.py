"""The analysis of a pack version: a report the administrator reads before validating.

Each finding has a level — ``blocking`` (the version cannot be published), ``warning`` (it can, knowingly),
``info`` — a code (translated by the interface) and its parameters. What it checks:

- the manifests, the files they name, their kinds and sizes, the look keys (a built-in look or another pack's
  is a conflict: blocking unless the element declares it ``replaces`` it, then a warning);
- CSS: imports and addresses outside the pack, rules not scoped to the look (they could restyle the whole
  site), fixed positions;
- GLSL: the contract of its kind (a stage or a shape writes ``o``; an ambience has its own ``main``), names
  GLSL reserves or the portal already declares;
- JS (the administrator's responsibility, flagged ``script``): network calls, Portalab's API, the browser's
  storage and cookies, ``eval``, the default export the interface mounts;
- the economy each element proposes (rarity, price, level against Portalab's own rules) and its texts;
- packs and boosters: the products they hold; booster scenes: their parts and durations;
- widgets: the data contracts they ask for (only the portal's), their sizes and pace.

The simulation (compiling, frames per second in a real browser) is added later by the sandbox.
"""

import json
import re
from collections.abc import Iterable, Mapping
from pathlib import PurePosixPath
from typing import Any

from portalab.capabilities.visuals import (
    LOOK_TYPES,
    PACK_LOOKS,
    InterfaceRegistry,
    contract_known,
    live_looks,
)
from portalab.modules.visuals.manifest import (
    GIVEABLE,
    LOOK_FIELD,
    PAYLOAD_FIELDS,
    RARITIES,
    SCENE_PARTS,
    TYPES,
    Element,
    ManifestError,
    Pack,
    parse_element,
    parse_pack,
    safe_relative,
)
from portalab.modules.visuals.store import ALLOWED, Files

GREAT_TIERS = (10, 20, 30, 40, 50)
# a price that would surprise next to Portalab's own catalog, per rarity (Coins)
USUAL_PRICES = {"common": (50, 700), "rare": (300, 1200), "epic": (600, 2500), "legendary": (1000, 6000)}
NETWORK = re.compile(r"\b(fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon)\b")
STORAGE = re.compile(r"\b(document\.cookie|localStorage|sessionStorage|indexedDB)\b")
DYNAMIC = re.compile(r"\beval\s*\(|\bnew\s+Function\s*\(")
# an interface renames its navigation, its pages' titles and the value names (never an action, a price, a
# warning: what a member confirms stays Portalab's words)
VOCABULARY = re.compile(r"nav:nav\.[\w.]+|[a-z]+:([\w.]+\.)?title|gamification:value\.\w+")
# 028: the words of a navigation's own chrome (``shell:<navigation>.<word>``: a taskbar's « Start », a d-pad's
# « Menu »…) and the menu button — never an action, a price or a confirmation
NAVIGATION_WORD = re.compile(r"shell:menu|shell:([a-z][a-z0-9-]*)\.\w+")


def vocabulary_key_ok(key: str) -> bool:
    """A text an interface may rename: a navigation's entry or title, a page's title, a value's label, a word
    of one of Portalab's navigations."""
    if VOCABULARY.fullmatch(key):
        return True
    word = NAVIGATION_WORD.fullmatch(key)
    return bool(word) and (word.group(1) is None or word.group(1) in live_looks.shipped("navigation"))


GLSL_RESERVED = re.compile(r"\b(?:float|vec[234]|int)\s+(out|in|input|output|sample|filter|active)\b")
# what the portal declares before a look's body (``p``, ``ax``, ``d``, ``t``, ``o``): declared again at the
# body's own level, it does not compile (a loop or a block of its own may shadow them)
GLSL_GIVEN = re.compile(r"\b(?:float|int|bool|vec[234]|mat[234])\s+(p|ax|d|t|o)\s*[=;,]")
# what the Security step shows: what a pack's files would try and what Portalab refuses
SECURITY_CODES = re.compile(
    r"^(css\.|js\.|file\.(unsafe|kind)|theme\.vocabulary|look\.(replaces|builtin|taken))"
)


def category_of(code: str) -> str:
    return "security" if SECURITY_CODES.match(code) else "analysis"


class Report:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []
        self.elements: list[dict[str, Any]] = []

    def add(self, severity: str, code: str, element: str | None = None, **params: Any) -> None:
        self.items.append(
            {
                "level": severity,
                "code": code,
                "category": category_of(code),
                "element": element,
                "params": params,
            }
        )

    def counts(self) -> dict[str, int]:
        return {
            level: sum(i["level"] == level for i in self.items) for level in ("blocking", "warning", "info")
        }

    def out(self, pack: Pack | None) -> dict[str, Any]:
        counts = self.counts()
        return {
            "summary": {
                **counts,
                "elements": len(self.elements),
                "hd": any(e["hd"] for e in self.elements),
                "script": any(e["script"] for e in self.elements),
                "publishable": counts["blocking"] == 0,
                "security": {
                    level: sum(i["level"] == level and i["category"] == "security" for i in self.items)
                    for level in ("blocking", "warning", "info")
                },
            },
            "pack": pack.model_dump() if pack else None,
            "items": self.items,
            "elements": self.elements,
        }


def element_folders(files: Files, pack: Pack) -> list[str]:
    if pack.elements is not None:
        return [e.strip("/") for e in pack.elements]
    found = {
        PurePosixPath(name).parent.as_posix()
        for name in files.entries
        if PurePosixPath(name).name == "element.json" and name.startswith("elements/")
    }
    return sorted(found)


def analyse(
    files: Files,
    *,
    taken: Mapping[tuple[str, str], str] | None = None,
    products_taken: Mapping[str, str] | None = None,
    interfaces: InterfaceRegistry | None = None,
    builtin: bool = False,
) -> dict[str, Any]:
    """The report of a version. ``taken``: (type, look) → the pack holding it; ``products_taken``: product
    key → the pack holding it (other packs' only: a pack updating its own keys is a new version);
    ``interfaces``: UI's validation of interface definitions (without it, an interface cannot be checked —
    blocking); ``builtin``: a pack Portalab ships (its looks are the built-in ones, never a conflict)."""
    report = Report()
    raw = files.get("pack.json")
    if raw is None:
        report.add("blocking", "pack.missing")
        return report.out(None)
    try:
        pack = parse_pack(raw)
    except ManifestError as error:
        report.add("blocking", "pack.invalid", detail=str(error))
        return report.out(None)
    _texts(report, pack.names.model_dump(), None)
    if not pack.license:
        report.add("info", "pack.no_license")
    if not re.fullmatch(r"v?\d+(\.\d+){1,3}(-[\w.]+)?(\+[\w.]+)?", pack.version):
        report.add("warning", "pack.version_format", version=pack.version)
    for name in files.entries:
        suffix = PurePosixPath(name).suffix.lower()
        if suffix not in ALLOWED:
            report.add("blocking", "file.kind", file=name, suffix=suffix or "(none)")
    folders = element_folders(files, pack)
    if not folders:
        report.add("blocking", "pack.empty")
    elements: list[tuple[str, Element]] = []
    for folder in folders:
        data = files.get(f"{folder}/element.json")
        if data is None:
            report.add("blocking", "element.missing", folder=folder)
            continue
        try:
            elements.append((folder, parse_element(data, folder)))
        except ManifestError as error:
            report.add("blocking", "element.invalid", folder=folder, detail=str(error))
    keys = [element.product_key for _, element in elements if element.sold]
    for key in {k for k in keys if keys.count(k) > 1}:
        report.add("blocking", "element.duplicate", key)
    own_products = set(keys)
    own_looks = frozenset((e.type, e.look) for _, e in elements if e.look)
    for folder, element in elements:
        _element(
            report,
            files,
            folder,
            element,
            own_products,
            taken or {},
            products_taken or {},
            own_looks,
            interfaces=interfaces,
            builtin=builtin,
            scene_parts={f: e.type for f, e in elements if e.type in SCENE_PARTS},
            widgets={e.look: e.payload.get("options") for _, e in elements if e.type == "widget" and e.look},
        )
    return report.out(pack)


def _texts(report: Report, names: Mapping[str, str], element: str | None) -> None:
    for language in ("fr", "en"):
        if not names.get(language):
            report.add("warning", "text.missing", element, language=language)


def _element(
    report: Report,
    files: Files,
    folder: str,
    element: Element,
    own_products: set[str],
    taken: Mapping[tuple[str, str], str],
    products_taken: Mapping[str, str],
    own_looks: frozenset[tuple[str, str]] = frozenset(),
    *,
    interfaces: InterfaceRegistry | None = None,
    builtin: bool = False,
    scene_parts: dict[str, str] | None = None,
    widgets: Mapping[str, Any] | None = None,
) -> None:
    key = element.product_key
    kind = element.render.kind
    allowed = TYPES.get(element.type)
    if allowed is None:
        report.add("blocking", "element.type", key, type=element.type)
        return
    if kind not in allowed[0] and kind != "renderer":
        report.add("blocking", "render.kind", key, kind=kind, type=element.type, allowed=sorted(allowed[0]))
    if kind == "renderer" and element.render.renderer == "builtin" and not builtin:
        report.add("blocking", "render.builtin_reserved", key)  # Portalab's own looks, by their own code
    # a title or a badge may wear a built-in style (its look then optional)
    held_in_payload = builtin and LOOK_FIELD.get(element.type) in element.payload  # a look two products sell
    if (
        element.type in LOOK_FIELD
        and element.type not in ("badge", "title")
        and not element.look
        and not held_in_payload
    ):
        report.add("blocking", "element.no_look", key)
    _texts(report, element.names.model_dump(), key)
    # the files it names: inside its folder, present, of a kind it may use
    for name in element.files():
        if not safe_relative(name):
            report.add("blocking", "file.unsafe", key, file=name)
            continue
        if files.get(f"{folder}/{name}") is None:
            report.add("blocking", "file.missing", key, file=name)
    if kind in ("glsl", "js", "theme") and not element.render.file:
        report.add("blocking", "render.no_file", key, kind=kind)
    if kind == "renderer" and not element.render.renderer:
        report.add("blocking", "render.no_renderer", key)
    if not element.preview and not builtin:
        report.add("info", "element.no_preview", key)
    # the look: one of Portalab's own packs' or another pack's is a conflict
    if (
        element.look
        and element.type in LOOK_TYPES
        and not builtin
        and element.look in live_looks.shipped(element.type)
    ):
        if element.replaces:
            report.add("warning", "look.replaces_builtin", key, look=element.look)
        else:
            report.add("blocking", "look.builtin", key, look=element.look)
    owner = taken.get((element.type, element.look)) if element.look else None
    if owner:
        if element.replaces:
            report.add("warning", "look.replaces", key, look=element.look, pack=owner)
        else:
            report.add("blocking", "look.taken", key, look=element.look, pack=owner)
    if key in products_taken and element.sold:
        report.add("blocking", "product.taken", key, pack=products_taken[key])
    css = [files.get(f"{folder}/{name}") or b"" for name in element.render.css]
    for name, data in zip(element.render.css, css, strict=True):
        _css(report, key, element, name, data.decode("utf-8", "replace"))
    main = files.get(f"{folder}/{element.render.file}") if element.render.file else None
    source = main.decode("utf-8", "replace") if main else ""
    if kind == "glsl" and main is not None:
        _glsl(report, key, element, source)
    if kind == "js" and main is not None:
        _js(report, key, source)
    if kind == "theme" and main is not None:
        _theme(report, key, element, source, own_looks, interfaces, builtin=builtin)
    if element.sold:
        _economy(report, key, element)
    if element.type == "navigation" and element.render.nav is None:
        report.add("info", "nav.default_layout", key)
    own_field = {LOOK_FIELD[element.type]} if held_in_payload else set()
    extra = sorted(set(element.payload) - PAYLOAD_FIELDS.get(element.type, frozenset()) - own_field)
    if extra:
        report.add("blocking", "payload.fields", key, fields=extra)
    if element.type == "bundle":
        _bundle(report, key, element, own_products)
    if element.type == "booster_scene":
        _scene(report, key, element, scene_parts)
    if element.type in ("booster_opening", "card_reveal") and (element.render.duration or 0) > (
        4 if element.type == "booster_opening" else 3
    ):
        report.add("blocking", "scene.duration", key, seconds=element.render.duration)
    if not element.economy.sold and element.type not in GIVEABLE:
        report.add("blocking", "economy.not_giveable", key, type=element.type)
    if element.type == "widget_option":
        _widget_option(report, key, element, widgets or {})
    if element.type == "widget":
        _widget(report, key, element)
    elif element.type == "widget_option" and element.render.kind == "js":
        _contracts(report, key, element)
    elif element.contracts:
        report.add("blocking", "widget.contracts_elsewhere", key)  # only a widget is handed data
    if element.type == "palette" and kind != "renderer":  # a built-in palette's colours are in its renderer
        _palette(report, key, element)
    report.elements.append(
        {
            "folder": folder,
            "product": key,
            "type": element.type,
            "look": element.look,
            "kind": kind,
            "folder_files": element.files(),
            "contracts": element.contracts,
            "free": element.free,
            "hd": kind == "glsl",
            "script": kind == "js",
            "names": element.names.model_dump(),
            "descriptions": element.descriptions.model_dump(),
            "economy": element.economy.model_dump(),
            "payload": element.payload,
            "render": element.render.model_dump(),
            "palette": element.palette,
            "preview": element.preview,
            "replaces": element.replaces,
            "bytes": sum(len(files.get(f"{folder}/{n}") or b"") for n in element.files()),
        }
    )


def _step(char: str) -> int:
    return 1 if char in "([" else -1 if char in ")]" else 0


def selectors_of(text: str) -> list[str]:
    """The selectors of a stylesheet (comments, keyframes and font faces left out; the rules inside
    @media/@supports/@container/@layer kept), each one alone (commas inside parentheses respected)."""
    body = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    body = re.sub(
        r"@(font-face|(-webkit-)?keyframes|property|counter-style)[^{]*\{(?:[^{}]|\{[^{}]*\})*\}", "", body
    )
    body = re.sub(r"@[\w-]+[^{};]*\{", "", body)  # the opening of the other at-rules
    out: list[str] = []
    for block in re.findall(r"([^{};]+)\{", body):
        depth, start = 0, 0
        for index, char in enumerate(block):
            depth += _step(char)
            if char == "," and depth == 0:
                out.append(block[start:index].strip())
                start = index + 1
        out.append(block[start:].strip())
    return [s for s in out if s]


# a sibling combinator (``~``, ``+`` — not the attribute operator ``~=``), :has(), the document's root
ESCAPES = re.compile(r"\+|~(?!=)|:has\(|:root|(?:^|[\s>(,])(?:html|body)\b")
# the An+B formula of ``:nth-child(3n + 1)``… is not a combinator (its ``of S`` part is still checked)
NTH = re.compile(r":nth-[a-z-]+\(\s*(?:[-+]?\d*n\s*(?:[-+]\s*\d+)?|[-+]?\d+|odd|even)\s*", re.I)


def _first_compound(selector: str) -> str:
    depth = 0
    for index, char in enumerate(selector):
        depth += _step(char)
        if depth == 0 and (char.isspace() or char in ">~+"):
            return selector[:index]
    return selector


def look_selector_ok(selector: str, look: str) -> bool:
    """A look styles its own element only: its hook (``[data-…="<look>"]``, or ``~=`` where an element wears
    several — a widget's options) on the selector's first part, then only what is inside it (no sibling
    combinator, no :has(), never the document's root)."""
    hook = re.search(
        r"\[data-[\w-]+~?=(?:\""
        + re.escape(look)
        + r"\"|'"
        + re.escape(look)
        + r"'|"
        + re.escape(look)
        + r")\]",
        _first_compound(selector),
    )
    return bool(hook) and not ESCAPES.search(NTH.sub(":nth(", selector))


def interface_selector_ok(selector: str, key: str) -> bool:
    """An interface styles the whole interface — under its own key, never a protected surface (the
    interface adds that exclusion when it loads the sheet)."""
    first = _first_compound(selector)
    return bool(
        re.fullmatch(
            r"(?::root|html)?\[data-theme=(?:\"" + re.escape(key) + r"\"|'" + re.escape(key) + r"')\]", first
        )
    )


def _css(report: Report, key: str, element: Element, name: str, text: str) -> None:
    if re.search(r"@import\b", text):
        report.add("blocking", "css.import", key, file=name)
    for address in re.findall(r"url\(\s*['\"]?([^'\")]+)", text):
        if re.match(r"^((https?|ftp|javascript|file):|//)", address.strip(), re.I):
            report.add("blocking", "css.external_url", key, file=name, url=address.strip()[:120])
    if re.search(r"position\s*:\s*fixed", text):
        report.add("info", "css.fixed", key, file=name)
    if not element.look:
        return
    selectors = [s for s in selectors_of(text) if not re.fullmatch(r"(from|to|[\d.]+%)(\s*,\s*[\d.]+%)*", s)]
    if element.type == "theme":
        loose = [s for s in selectors if not interface_selector_ok(s, element.look)]
        if loose:
            report.add(
                "blocking", "css.interface_scope", key, file=name, look=element.look, selectors=loose[:3]
            )
        return
    loose = [s for s in selectors if not look_selector_ok(s, element.look)]
    if loose:
        report.add("blocking", "css.unscoped", key, file=name, look=element.look, selectors=loose[:3])


def _glsl(report: Report, key: str, element: Element, source: str) -> None:
    if element.type in ("ambient", "profile_background"):
        if "void main" not in source or "gl_FragColor" not in source:
            report.add("blocking", "glsl.ambient_contract", key)
    elif not re.search(r"\bo\s*=", source):
        report.add("blocking", "glsl.shape_contract", key)
    if element.type in ("level_up", "effect") and not element.render.stage:
        report.add("warning", "glsl.not_stage", key)
    for name in sorted(set(GLSL_RESERVED.findall(source))):
        report.add("blocking", "glsl.reserved", key, name=name)
    if element.type not in ("ambient", "profile_background"):
        for name in sorted(_redeclared(source)):
            report.add("blocking", "glsl.reserved", key, name=name)
    if len(source) > 60_000:
        report.add("warning", "glsl.large", key, size=len(source))
    if element.type in ("level_up", "effect") and "u_age" not in source:
        report.add("info", "glsl.no_timeline", key)


def _widget(report: Report, key: str, element: Element) -> None:
    """A pack's widget: the data it asks for among the portal's contracts, the sizes it may take on the
    dashboard (columns of 12, rows), how often it is read again."""
    _contracts(report, key, element)
    if not element.contracts:
        report.add("info", "widget.no_contract", key)  # a clock, a picture: it needs nothing of the portal
    sizes = element.payload.get("sizes")
    valid = isinstance(sizes, list) and 0 < len(sizes) <= 6
    for size in sizes if isinstance(sizes, list) else []:
        w = size.get("w") if isinstance(size, dict) else None
        h = size.get("h") if isinstance(size, dict) else None
        if not (isinstance(w, int) and isinstance(h, int) and 1 <= w <= 12 and 1 <= h <= 6):
            valid = False
    if sizes is not None and not valid:
        report.add("blocking", "widget.size", key)
    refresh = element.payload.get("refresh_s")
    if refresh is not None and not (isinstance(refresh, int) and 30 <= refresh <= 3600):
        report.add("blocking", "widget.refresh", key)
    empty = element.payload.get("empty")
    if empty is not None and not (
        isinstance(empty, dict) and all(isinstance(v, str) and len(v) <= 200 for v in empty.values())
    ):
        report.add("blocking", "widget.empty", key)
    if element.payload.get("options") is not None and settings_of(element.payload.get("options")) is None:
        report.add("blocking", "widget.options", key)


SETTING = re.compile(r"^[a-z][a-z0-9_-]{0,23}$")


def _texts_ok(value: Any) -> bool:
    return isinstance(value, dict) and all(isinstance(v, str) and len(v) <= 80 for v in value.values())


def settings_of(options: Any) -> dict[str, tuple[list[str], str]] | None:
    """A pack widget's own settings (``payload.options``): each its key, its values and its default — or
    ``None`` when they are not well formed (6 settings at most, 2 to 12 values each, names short)."""
    if not isinstance(options, list) or len(options) > 6:
        return None
    out: dict[str, tuple[list[str], str]] = {}
    for option in options:
        if not isinstance(option, dict) or not SETTING.fullmatch(str(option.get("key", ""))):
            return None
        values = option.get("values")
        if not isinstance(values, list) or not 2 <= len(values) <= 12:
            return None
        keys = []
        for value in values:
            if not isinstance(value, dict) or not SETTING.fullmatch(str(value.get("value", ""))):
                return None
            if not _texts_ok(value.get("names", {})):
                return None
            keys.append(str(value["value"]))
        default = str(option.get("default", keys[0]))
        if len(set(keys)) != len(keys) or default not in keys or not _texts_ok(option.get("names", {})):
            return None
        out[str(option["key"])] = (keys, default)
    return out


def _contracts(report: Report, key: str, element: Element) -> None:
    for contract in element.contracts:
        if not contract_known(contract):
            report.add("blocking", "widget.unknown_contract", key, contract=contract)
    if len(set(element.contracts)) != len(element.contracts):
        report.add("warning", "widget.contract_twice", key)


def own_widget(target: Any) -> str | None:
    """The look of this pack's widget an option names (``<look>`` or ``pack.<look>``)."""
    if not isinstance(target, str):
        return None
    return target.removeprefix("pack.") if target.startswith("pack.") or "." not in target else None


def _widget_option(report: Report, key: str, element: Element, widgets: Mapping[str, Any]) -> None:
    """An option of a widget. A value of one of this pack's widgets' own settings (``setting``, ``value``:
    data only; its default is everyone's, never sold), or an add-on a widget wears — Portalab's (its key),
    this pack's, or any (``*``): a stylesheet under ``[data-widget-option~="<look>"]`` (animations, another
    look) and/or a script in the sandbox, shown instead of the widget's content or drawn over it (``place``),
    handed the widget's own data and the contracts it declares."""
    payload = element.payload
    if "setting" not in payload:
        target = payload.get("widget")
        valid_target = target == "*" or (
            isinstance(target, str)
            and re.fullmatch(r"[a-z0-9][a-z0-9_.:-]{0,95}", target) is not None
            and (own_widget(target) in widgets if own_widget(target) is not None else "." in target)
        )
        if not valid_target:
            report.add("blocking", "widget.option_target", key, widget=str(target))
        if not element.look:
            report.add("blocking", "element.no_look", key)
        if element.render.kind == "data":
            report.add("blocking", "widget.option_empty", key)  # an add-on brings a stylesheet or a script
        if element.render.kind == "js" and element.render.place is None:
            report.add("blocking", "widget.option_place", key)
        return
    if element.render.kind != "data":
        report.add("blocking", "widget.option_value_drawn", key)  # the widget's own script draws its values
    widget = own_widget(payload.get("widget"))
    settings = settings_of(widgets.get(widget)) if widget is not None and widget in widgets else None
    known = settings.get(str(payload.get("setting"))) if settings else None
    if known is None or str(payload.get("value")) not in known[0]:
        report.add("blocking", "widget.option_unknown", key, widget=str(widget))
    elif str(payload.get("value")) == known[1]:
        report.add("warning", "widget.option_default", key)


def _redeclared(source: str) -> set[str]:
    """The given names a body declares again at its own level (outside any block of its own)."""
    text = re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.S)
    text = re.sub(r"\bfor\s*\([^)]*\)", "for", text)  # a loop's own counter is its own
    found: set[str] = set()
    depth = 0
    start = 0
    for index, char in enumerate(text + "{"):
        if char in "{}":
            if depth == 0:
                found.update(GLSL_GIVEN.findall(text[start:index]))
            depth = max(0, depth + (1 if char == "{" else -1))
            start = index + 1
    return found


def _js(report: Report, key: str, source: str) -> None:
    """A script runs in a sandbox (no account, no network, no page of Portalab): what it would try beyond is
    noted — it will be refused there."""
    report.add("info", "js.sandboxed", key)
    if not re.search(r"\bexport\s+default\b", source):
        report.add("blocking", "js.no_export", key)
    if re.search(r"^\s*import\s.+\sfrom\s|^\s*import\s*['\"]", source, re.M):
        report.add("blocking", "js.static_import", key)
    if NETWORK.search(source):
        report.add("info", "js.network", key, calls=sorted(set(NETWORK.findall(source))))
    if "/api/" in source:
        report.add("info", "js.portal_api", key)
    if STORAGE.search(source):
        report.add("info", "js.storage", key, uses=sorted(set(STORAGE.findall(source))))
    if DYNAMIC.search(source):
        report.add("warning", "js.dynamic_code", key)
    if len(source) > 400_000:
        report.add("warning", "js.large", key, size=len(source))


def _theme(
    report: Report,
    key: str,
    element: Element,
    source: str,
    own_looks: frozenset[tuple[str, str]],
    interfaces: InterfaceRegistry | None,
    *,
    builtin: bool = False,
) -> None:
    """An interface: a valid definition (it may name the pack's own looks), its key the look's, above the
    accessibility floor, not a built-in interface's key."""
    try:
        document = json.loads(source)
    except ValueError as error:
        report.add("blocking", "theme.invalid", key, detail=str(error)[:200])
        return
    if interfaces is None:
        report.add("blocking", "theme.unchecked", key)
        return
    token = PACK_LOOKS.set(own_looks)
    try:
        theme_key, errors, floor = interfaces.validate(document)
    finally:
        PACK_LOOKS.reset(token)
    if theme_key is None or floor is None:
        report.add("blocking", "theme.invalid", key, detail="; ".join(errors[:4]))
        return
    if theme_key != element.look:
        report.add("blocking", "theme.key", key, theme=theme_key, look=element.look)
    if not builtin and theme_key in interfaces.builtin_keys():
        report.add("blocking", "look.builtin", key, look=theme_key)
    if not floor["ok"]:
        found: Any = floor.get("violations") or []
        violations: list[Any] = list(found)
        report.add("blocking", "theme.floor", key, violations=[str(v) for v in violations][:4])
    words = (document.get("vocabulary") or {}).values()
    foreign = sorted({k for language in words for k in language if not vocabulary_key_ok(k)})
    if foreign:
        report.add("blocking", "theme.vocabulary", key, keys=foreign[:5])
    navigation = document.get("layout", {}).get("nav", {})
    if navigation:
        report.add("info", "theme.nav", key, nav=sorted(set(navigation.values())))


def _economy(report: Report, key: str, element: Element) -> None:
    economy = element.economy
    if economy.rarity not in RARITIES:
        report.add("blocking", "economy.rarity", key, rarity=economy.rarity)
        return
    if not economy.sold:
        report.add("info", "economy.given", key)  # 028: offered to everyone, never a shop product
        return
    if economy.price is None and element.type not in ("bundle",):
        report.add("info", "economy.reward_only", key)
    low, high = USUAL_PRICES[economy.rarity]
    if economy.price is not None and not low <= economy.price <= high and element.type != "bundle":
        report.add("info", "economy.price_unusual", key, price=economy.price, low=low, high=high)
    if economy.level and economy.level > 50:
        report.add("warning", "economy.level_high", key, level=economy.level)
    if economy.rarity == "legendary" and economy.level and economy.level not in GREAT_TIERS:
        report.add("info", "economy.legendary_tier", key, level=economy.level)


def _bundle(report: Report, key: str, element: Element, own_products: set[str]) -> None:
    held = element.payload.get("products")
    if not isinstance(held, list) or not held:
        report.add("blocking", "bundle.empty", key)
        return
    foreign = [p for p in held if isinstance(p, str) and p not in own_products]
    if foreign:
        report.add("info", "bundle.outside", key, products=foreign[:8])


SLOT_TYPES = {
    "booster_look": "booster_look",
    "backdrop": "booster_backdrop",
    "opening": "booster_opening",
    "reveal": "card_reveal",
    "face": "card_face",
    "back": "card_back",
}


def _scene(report: Report, key: str, element: Element, parts: dict[str, str] | None) -> None:
    """A booster scene names its parts — folders of its own pack, of the right type, per rarity where a part
    depends on it."""
    named = element.payload.get("parts")
    if not isinstance(named, dict) or not named:
        report.add("blocking", "scene.empty", key)
        return
    folders = {f.removeprefix("elements/"): t for f, t in (parts or {}).items()}
    for slot, value in named.items():
        wanted = SLOT_TYPES.get(slot)
        if wanted is None:
            report.add("blocking", "scene.slot", key, slot=slot)
            continue
        targets = value.items() if isinstance(value, dict) else [("all", value)]
        for rarity, folder in targets:
            if rarity != "all" and rarity not in RARITIES:
                report.add("blocking", "scene.rarity", key, slot=slot, rarity=rarity)
            if folders.get(str(folder).removeprefix("elements/")) != wanted:
                report.add("blocking", "scene.part", key, slot=slot, part=str(folder))


def _palette(report: Report, key: str, element: Element) -> None:
    colours = element.palette or {}
    for scheme in ("dark", "light"):
        values = colours.get(scheme) or {}
        if not all(re.fullmatch(r"#[0-9a-fA-F]{6}", str(values.get(n, ""))) for n in ("accent", "accentAlt")):
            report.add("blocking", "palette.colours", key, scheme=scheme)


def looks_of(report: Mapping[str, Any]) -> Iterable[tuple[str, str]]:
    for element in report.get("elements", []):
        if element.get("look") and element["type"] in LOOK_TYPES:
            yield element["type"], element["look"]
