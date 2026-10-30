"""The format of a visual pack (``format: 1``, specs/028-visual-packs/contracts/pack-format.md):
``pack.json`` at its root, one ``element.json`` per element.

An element is a look, mostly sold in the shop: its type (``level_up``, ``avatar_frame``…), the look's key
(``look``: what preferences and profiles store, what the interface's ``data-*`` attributes carry), how it is
drawn (``render``: CSS, a GLSL fragment, a JS module, an interface definition, a portal renderer with its
parameters, or data only for packs, boosters, titles and badges), the economy it proposes (price, rarity,
level, copies — the administrator decides at review) and its texts.
"""

import json
import re
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

KEY = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
RARITIES = ("common", "rare", "epic", "legendary")
RenderKind = Literal["css", "glsl", "js", "video", "theme", "data", "renderer", "none"]  # ``none``: ``data``

# what each type of element may be drawn with, and the prefix of its product key
TYPES: dict[str, tuple[frozenset[str], str]] = {
    "level_up": (frozenset({"css", "glsl", "js"}), "levelup"),
    "effect": (frozenset({"css", "glsl", "js"}), "effect"),
    "ambient": (frozenset({"css", "glsl", "renderer"}), "ambient"),  # renderer: Portalab's layers (flow…)
    "profile_background": (frozenset({"css", "glsl"}), "bg"),
    "avatar_frame": (frozenset({"css", "glsl"}), "frame"),
    "profile_banner": (frozenset({"css"}), "banner"),
    "name_style": (frozenset({"css", "glsl"}), "name"),
    "level_badge": (frozenset({"css", "glsl"}), "level"),
    "notification_style": (frozenset({"css", "glsl"}), "notif"),
    "notification_animation": (frozenset({"css", "glsl"}), "notif"),
    "palette": (frozenset({"data"}), "palette"),
    "badge": (frozenset({"css", "glsl", "data"}), "badge"),
    "title": (frozenset({"css", "glsl", "data"}), "title"),
    "bundle": (frozenset({"data"}), "pack"),
    "theme_pack": (frozenset({"data"}), "pack"),
    "booster": (frozenset({"data"}), "booster"),
    # the booster scene and its parts (drawn around the cards Portalab draws itself)
    "booster_scene": (frozenset({"data"}), "scene"),
    "booster_look": (frozenset({"css", "glsl"}), "booster_look"),
    # the stage's animated background
    "booster_backdrop": (frozenset({"css", "glsl", "js", "video"}), "booster_backdrop"),
    "booster_opening": (frozenset({"css", "glsl", "js", "video"}), "booster_opening"),
    "card_reveal": (frozenset({"css", "glsl", "js", "video"}), "card_reveal"),
    "card_face": (frozenset({"css", "glsl"}), "card_face"),
    "card_back": (frozenset({"css", "glsl"}), "card_back"),
    # issue 233: an edition's frame for the media cards (its look ``edition-<edition>``: the cards of that
    # edition's version wear it, Portalab drawing the card and its texts)
    "card_frame": (frozenset({"css"}), "card_frame"),
    # widgets: a style for the existing ones, or a widget of its own (a script fed by data contracts)
    "widget_style": (frozenset({"css"}), "widget_style"),
    "widget": (frozenset({"js"}), "widget"),
    # an option of a widget — Portalab's or a pack's: an add-on it wears (a stylesheet, animations; a script
    # showing it otherwise, with more data, or drawing over it) or a value of a pack widget's own setting
    "widget_option": (frozenset({"data", "css", "js"}), "widget_option"),
    # an interface: its definition (``theme.json``: colours, fonts, layout, navigation, vocabulary, the
    # looks it wears) and stylesheets of its own
    "theme": (frozenset({"theme"}), "theme"),
    # a navigation of its own, for interfaces: a script drawing it in a sandbox (never sold on its own)
    "navigation": (frozenset({"js", "renderer"}), "nav"),
}
# what is not a shop product: an interface, a booster or a scene wears it
NOT_SOLD = frozenset(
    {
        "navigation",
        "booster_scene",
        "booster_backdrop",
        "booster_look",
        "booster_opening",
        "card_reveal",
        "card_face",
        "card_back",
        "card_frame",
    }
)
# the parts of a booster scene, and the rarities a part may be bound to
SCENE_PARTS = frozenset(
    {"booster_look", "booster_backdrop", "booster_opening", "card_reveal", "card_face", "card_back"}
)
# what the administrator may give everyone rather than sell (``economy.sold: false``): no shop product, every
# member may use it — a widget, its looks and its settings' values
GIVEABLE = frozenset({"widget", "widget_style", "widget_option"})
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
    "widget_style": "style",
}
# the settings each type takes in its payload besides the look (the shop refuses any other)
PAYLOAD_FIELDS: dict[str, frozenset[str]] = {
    "badge": frozenset({"label", "icon", "style"}),  # ``style``: a built-in style, when it brings none
    "title": frozenset({"label", "style"}),
    "bundle": frozenset({"products"}),
    "theme_pack": frozenset({"products"}),
    "booster_scene": frozenset({"parts"}),
    "widget_style": frozenset({"widget"}),
    "widget": frozenset({"sizes", "refresh_s", "empty", "options"}),
    "widget_option": frozenset({"widget", "setting", "value"}),
    "booster": frozenset(
        {"pool", "season", "packs", "items", "cards", "odds", "guarantee", "refunds", "per_member", "look"}
    ),
}


class Texts(BaseModel):
    model_config = ConfigDict(extra="allow")
    fr: str = Field(default="", max_length=1000)
    en: str = Field(default="", max_length=1000)


class NavLayout(BaseModel):
    """Where a navigation sits, said before its script runs (Portalab keeps its room): a bar along an edge,
    a floating button, its size; ``expands``: it may cover the screen while open."""

    model_config = ConfigDict(extra="forbid")
    position: Literal["top", "bottom", "left", "right", "floating"] = "bottom"
    size: int = Field(default=72, ge=40, le=320)  # CSS pixels (the bar's height or width, the button's side)
    expands: bool = False


class Render(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: RenderKind = "data"
    file: str | None = None  # the GLSL fragment, the JS module or the video
    css: list[str] = Field(default_factory=list)  # stylesheets (fonts declared in them, relative URLs)
    stage: bool = False  # GLSL: drawn over the whole stage (level-ups, celebrations) rather than a shape
    # GLSL: 0 rounded box, 1 hexagon, 2 diamond, 3 shield, 4 star, 5 triangle (frames); 6 pointed ends,
    # 7 slanted, 8 wavy edges (wide shapes: notifications)
    shape: int = Field(default=0, ge=0, le=8)
    radius: str | None = Field(default=None, max_length=12)
    reveal: float | None = Field(default=None, ge=0, le=20)  # level-up: when the card shows (seconds)
    duration: float | None = Field(default=None, ge=0.5, le=30)  # how long it plays (seconds)
    start: float | None = Field(default=None, ge=0, le=20)  # GLSL stage: from when in its timeline it plays
    cycle: bool = False  # GLSL: comes and goes over and over (a portal as a teleporter)
    nav: NavLayout | None = None  # a navigation's place
    renderer: str | None = Field(default=None, max_length=40)  # ``renderer``: the portal renderer drawing it
    params: dict[str, Any] = Field(default_factory=dict)  # ``renderer``: its parameters
    rarity: Literal["common", "rare", "epic", "legendary"] | None = None  # scene parts: the rarity it is for
    # a widget option's script: shown instead of the widget's content, drawn over it (animations), or in the
    # region the widget keeps for it (``stage``: the daily wheel's face; the widget keeps its texts, controls)
    # issue 290: a card's reveal over the whole screen (``screen``): Portalab brings the card to the middle,
    # big, its videos behind and over it, the rarity's name written by Portalab over them
    place: Literal["replace", "overlay", "stage", "screen"] | None = None
    # issue 287: a video (a scene's backdrop plays it over and over, an opening or a reveal once) — its
    # transparency beside its picture (``side``: in its right half) or under it (``stacked``: its lower half),
    # in grey (white: opaque), which Portalab puts back together as it plays; ``over``: a reveal's second
    # video, played over the card (the first plays behind it)
    alpha: Literal["none", "side", "stacked"] = "none"
    over: str | None = None

    @field_validator("kind")
    @classmethod
    def _data(cls, value: str) -> str:
        return "data" if value == "none" else value  # the proof of concept's word for data only


class Economy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    price: int | None = Field(default=None, ge=0, le=1_000_000)
    rarity: str = "common"
    level: int | None = Field(default=None, ge=1, le=100)
    supply: int | None = Field(default=None, ge=1, le=1_000_000)
    collection: str | None = Field(default=None, max_length=40)
    icon: str | None = Field(default=None, max_length=40)
    repeatable: bool = False
    season: str | None = Field(default=None, max_length=20)
    # 028: what Portalab's own catalog needs to recreate its products as they are
    limit: tuple[int, int] | None = None  # purchases per member, per days
    featured: bool = False
    reward_only: bool = False  # given by an achievement or a level, never sold
    contribution: int | None = Field(default=None, ge=0)
    # 028 (US6): ``false`` — given to everyone, never a shop product (widgets, their looks and options only)
    sold: bool = True


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
    replaces: bool = False  # takes over a look of the same key held elsewhere (the administrator decides)
    contracts: list[str] = Field(default_factory=list, max_length=8)  # widgets: the data they ask for
    free: bool = False  # 028: a look everyone wears — never a shop product

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
        if self.type.startswith("plugin:"):  # 030: a plugin's kind of visual (``plugin:messenger.bubble``)
            prefix = self.type.removeprefix("plugin:").replace(".", "_")
        if self.type == "widget_option" and not self.look:  # named by what it sells: its widget's value
            what = f"{self.payload.get('widget', 'item')}_{self.payload.get('value', '')}"
            return f"{prefix}_{re.sub(r'[^a-z0-9_]', '_', what.lower())}"[:64]
        return f"{prefix}_{(self.look or 'item').replace('-', '_')}"

    @property
    def sold(self) -> bool:
        return not self.free and self.type not in NOT_SOLD

    def files(self) -> list[str]:
        return [f for f in (self.render.file, self.render.over, *self.render.css, self.preview) if f]


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
