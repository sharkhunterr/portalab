"""Declarative pages (spec 023 R12): a plugin page is a list of design-system blocks — sanitized Markdown,
stat/list/table/chart bound to the plugin's own data routes (typed states), and forms generated from a JSON
Schema that post to a plugin action. No plugin JavaScript ever runs in the SPA."""

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class MarkdownBlock:
    text: str
    kind: Literal["markdown"] = "markdown"


@dataclass(frozen=True, slots=True)
class DataBlock:
    """``stat`` / ``list`` / ``table`` / ``chart`` filled from ``GET /api/v1/plugins/<key>/<data>``."""

    kind: Literal["stat", "list", "table", "chart"]
    title_key: str
    data: str  # a plugin route path, e.g. "stats/today"
    columns: tuple[str, ...] = ()
    chart: Literal["line", "bar"] = "line"


@dataclass(frozen=True, slots=True)
class FormBlock:
    title_key: str
    schema: dict[str, Any]  # JSON Schema (object of scalar fields)
    action: str  # a plugin route path receiving the POST
    submit_key: str = "plugins:page.submit"
    kind: Literal["form"] = "form"


Block = MarkdownBlock | DataBlock | FormBlock


@dataclass(frozen=True, slots=True)
class PageDefinition:
    key: str  # unique within the plugin
    title_key: str
    required_permission: str
    blocks: tuple[Block, ...] = field(default_factory=tuple)
    nav_label_key: str | None = None  # also add a navigation entry to the page
