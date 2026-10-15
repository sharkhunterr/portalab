"""The format of a visual pack (``format: 1``): ``pack.json`` at its root, one ``element.json`` per element.

An element is one product of the shop: its type (``level_up``, ``avatar_frame``…), the look's key (``look``:
what preferences and profiles store, what the interface's ``data-*`` attributes carry), how it is drawn
(``render``: CSS, a GLSL fragment, a JS module, or nothing for packs, boosters, titles and badges), the
economy it proposes (price, rarity, level, copies — the administrator decides at validation) and its texts.
"""

import json
import re
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

KEY = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
RARITIES = ("common", "rare", "epic", "legendary")
RenderKind = Literal["css", "glsl", "js", "theme", "none"]

# what each type of element may be drawn with, and the prefix of its product key
TYPES: dict[str, tuple[frozenset[str], str]] = {
    "level_up": (frozenset({"css", "glsl", "js"}), "levelup"),
    "effect": (frozenset({"css", "glsl", "js"}), "effect"),
    "ambient": (frozenset({"css", "glsl"}), "ambient"),
    "profile_background": (frozenset({"css", "glsl"}), "bg"),
    "avatar_frame": (frozenset({"css", "glsl"}), "frame"),
    "profile_banner": (frozenset({"css"}), "banner"),
    "name_style": (frozenset({"css"}), "name"),
    "level_badge": (frozenset({"css", "glsl"}), "level"),
    "notification_style": (frozenset({"css"}), "notif"),
    "notification_animation": (frozenset({"css"}), "notif"),
    "palette": (frozenset({"none"}), "palette"),
    "badge": (frozenset({"css", "glsl", "none"}), "badge"),
    "title": (frozenset({"css", "glsl", "none"}), "title"),
    "bundle": (frozenset({"none"}), "pack"),
    "booster": (frozenset({"none"}), "booster"),
    # an interface: its definition (``theme.json``: colours, fonts, layout, navigation, vocabulary, the
    # looks it wears) and stylesheets of its own
    "theme": (frozenset({"theme"}), "theme"),
}
# the payload field naming the look, per type (packs, boosters: their own payload)
LOOK_FIELD = {
    "level_up": "animation",
    "effect": "effect",
    "ambient": "ambient",
    "profile_background": "background",
    "avatar_frame": "frame",
    "profile_banner": "banner",
    "name_style": "style",
    "level_badge": "style",
    "notification_style": "style",
    "notification_animation": "animation",
    "palette": "palette",
    "badge": "style",
    "title": "style",
    "theme": "theme",
}
# the settings each type takes in its payload besides the look (the shop refuses any other)
PAYLOAD_FIELDS: dict[str, frozenset[str]] = {
    "badge": frozenset({"label", "icon", "style"}),  # ``style``: a built-in style, when it brings none
    "title": frozenset({"label", "style"}),
    "bundle": frozenset({"products"}),
    "booster": frozenset(
        {"pool", "season", "packs", "cards", "odds", "guarantee", "refunds", "per_member", "look"}
    ),
}


class Texts(BaseModel):
    model_config = ConfigDict(extra="allow")
    fr: str = Field(default="", max_length=400)
    en: str = Field(default="", max_length=400)


class Render(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: RenderKind = "none"
    file: str | None = None  # the GLSL fragment or the JS module
    css: list[str] = Field(default_factory=list)  # stylesheets (fonts declared in them, relative URLs)
    stage: bool = False  # GLSL: drawn over the whole stage (level-ups, celebrations) rather than a shape
    shape: int = Field(default=0, ge=0, le=5)  # GLSL frames: 0 rounded box, 1 hexagon, 2 diamond, 3 shield…
    radius: str | None = Field(default=None, max_length=12)
    reveal: float | None = Field(default=None, ge=0, le=20)  # level-up: when the card shows (seconds)
    duration: float | None = Field(default=None, ge=0.5, le=30)  # how long it plays (seconds)


class Economy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    price: int | None = Field(default=None, ge=0, le=1_000_000)
    rarity: str = "common"
    level: int | None = Field(default=None, ge=1, le=100)
    supply: int | None = Field(default=None, ge=1, le=1_000_000)
    collection: str | None = Field(default=None, max_length=40)
    icon: str | None = Field(default=None, max_length=40)
    repeatable: bool = False


class Element(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    look: str | None = None
    product: str | None = None
    names: Texts
    descriptions: Texts = Field(default_factory=Texts)
    render: Render = Field(default_factory=Render)
    economy: Economy = Field(default_factory=Economy)
    payload: dict[str, Any] = Field(default_factory=dict)
    palette: dict[str, dict[str, str]] | None = None  # palettes: {dark: {accent…}, light: {…}}
    preview: str | None = None
    replaces: bool = False  # takes over a built-in look of the same key (validated by the administrator)

    @field_validator("look", "product")
    @classmethod
    def _key(cls, value: str | None) -> str | None:
        if value is not None and not KEY.fullmatch(value):
            raise ValueError("a key is lowercase letters, digits, - and _ (48 at most)")
        return value

    @property
    def product_key(self) -> str:
        if self.product:
            return self.product
        prefix = TYPES.get(self.type, (frozenset(), self.type))[1]
        return f"{prefix}_{(self.look or 'item').replace('-', '_')}"

    def files(self) -> list[str]:
        return [f for f in (self.render.file, *self.render.css, self.preview) if f]


class Pack(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal[1] = 1
    id: str
    version: str = Field(max_length=40)
    names: Texts
    descriptions: Texts = Field(default_factory=Texts)
    author: str | None = Field(default=None, max_length=120)
    license: str | None = Field(default=None, max_length=80)
    homepage: str | None = Field(default=None, max_length=300)
    elements: list[str] | None = None  # the elements' folders; every ``elements/*/element.json`` otherwise

    @field_validator("id")
    @classmethod
    def _id(cls, value: str) -> str:
        if not KEY.fullmatch(value):
            raise ValueError("a pack id is lowercase letters, digits, - and _ (48 at most)")
        return value


class ManifestError(ValueError):
    pass


def parse_json(raw: bytes | str, what: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ManifestError(f"{what} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError(f"{what} must be a JSON object")
    return data


def parse_pack(raw: bytes | str) -> Pack:
    try:
        return Pack.model_validate(parse_json(raw, "pack.json"))
    except ValidationError as exc:
        raise ManifestError(f"pack.json: {_errors(exc)}") from exc


def parse_element(raw: bytes | str, where: str) -> Element:
    try:
        return Element.model_validate(parse_json(raw, f"{where}/element.json"))
    except ValidationError as exc:
        raise ManifestError(f"{where}/element.json: {_errors(exc)}") from exc


def _errors(exc: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:5])


def safe_relative(path: str) -> bool:
    candidate = PurePosixPath(path)
    return bool(path) and not candidate.is_absolute() and ".." not in candidate.parts and "\\" not in path


def version_key(version: str) -> tuple[Any, ...]:
    """Orders versions (``1.10.0`` after ``1.9.2``; a pre-release before its release)."""
    main, _, pre = version.lstrip("vV").partition("-")
    parts = [int(p) if p.isdigit() else 0 for p in re.split(r"[.+]", main)][:4]
    return (*parts, *[0] * (4 - len(parts)), 0 if pre else 1, pre)
