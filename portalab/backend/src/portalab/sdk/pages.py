"""Declarative pages (spec 023 R12): a plugin page is a list of design-system blocks — sanitized Markdown,
stat/list/table/chart bound to the plugin's own data routes (typed states), and forms generated from a JSON
Schema that post to a plugin action. No plugin JavaScript ever runs in the SPA.

Spec 030 adds ``thread`` (messages with an author and a time) and ``cards`` (titles or people as Portalab's
cards) to the data blocks; the page's own address parameters (``?topic=12``) are passed to its data routes
and its forms."""

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class MarkdownBlock:
    text: str
    kind: Literal["markdown"] = "markdown"


@dataclass(frozen=True, slots=True)
class DataBlock:
    """``stat`` / ``list`` / ``table`` / ``chart`` / ``thread`` / ``cards`` filled from
    ``GET /api/v1/plugins/<key>/<data>``."""

    kind: Literal["stat", "list", "table", "chart", "thread", "cards", "checklist", "media"]
    title_key: str
    data: str  # a plugin route path, e.g. "stats/today"
    columns: tuple[str, ...] = ()
    chart: Literal["line", "bar"] = "line"
    action: str = ""  # 030 checklist: the route a ticked or unticked item is posted to
    live: str = ""  # 030: a live topic of the plugin; the block is read again when it says so


@dataclass(frozen=True, slots=True)
class FormBlock:
    title_key: str
    schema: dict[str, Any]  # JSON Schema (object of scalar fields)
    action: str  # a plugin route path receiving the POST
    submit_key: str = "plugins:page.submit"
    kind: Literal["form"] = "form"
    data: str = ""  # 030: a route giving the current values (``{"values": {...}}``), to edit


@dataclass(frozen=True, slots=True)
class ActionsBlock:
    """030: buttons — each opens one of the plugin's surfaces (``opens``) or posts to a route (``action``),
    then optionally goes to one of its pages (``then``); the page's parameters go along."""

    buttons: tuple[dict[str, str], ...] = ()
    kind: Literal["actions"] = "actions"


Block = MarkdownBlock | DataBlock | FormBlock | ActionsBlock


@dataclass(frozen=True, slots=True)
class PageDefinition:
    key: str  # unique within the plugin
    title_key: str
    required_permission: str
    blocks: tuple[Block, ...] = field(default_factory=tuple)
    nav_label_key: str | None = None  # also add a navigation entry to the page
