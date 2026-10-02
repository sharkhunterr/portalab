"""ICU MessageFormat in pure Python (spec 026 R3, T004/T009): parser + renderer with CLDR plural rules
from Babel — no system ICU library in the image. Supported: ``{arg}``, ``{arg, number[, integer|percent]}``,
``{arg, plural|selectordinal, [offset:N] =N {…} keyword {…}}`` with ``#``, ``{arg, select, … other {…}}``,
nesting, and ICU apostrophe quoting (``''``, ``'{…}'``, ``'#'``). Rendering never raises: a missing
argument renders as ``{name}`` and an unknown selector falls back to ``other``. Output is plain text."""

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from babel import Locale, UnknownLocaleError
from babel.numbers import format_decimal, format_percent
from babel.plural import PluralRule


class MessageSyntaxError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Text:
    value: str


@dataclass(frozen=True, slots=True)
class Pound:
    pass


@dataclass(frozen=True, slots=True)
class Arg:
    name: str
    kind: str  # "simple" | "number" | "plural" | "selectordinal" | "select"
    style: str | None = None
    offset: int = 0
    options: tuple[tuple[str, tuple[Any, ...]], ...] = ()


Node = Text | Pound | Arg


class _Parser:
    def __init__(self, source: str) -> None:
        self.s = source
        self.i = 0

    def fail(self, message: str) -> MessageSyntaxError:
        return MessageSyntaxError(f"{message} at position {self.i}")

    def ws(self) -> None:
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def message(self, in_plural: bool, depth: int = 0) -> tuple[Node, ...]:
        if depth > 10:
            raise self.fail("nesting too deep")
        nodes: list[Node] = []
        text: list[str] = []
        while self.i < len(self.s):
            c = self.s[self.i]
            if c == "'":
                nxt = self.s[self.i + 1] if self.i + 1 < len(self.s) else ""
                if nxt == "'":
                    text.append("'")
                    self.i += 2
                elif nxt in "{}" or (in_plural and nxt == "#"):
                    end = self.s.find("'", self.i + 1)
                    while end != -1 and end + 1 < len(self.s) and self.s[end + 1] == "'":
                        end = self.s.find("'", end + 2)
                    if end == -1:
                        text.append(self.s[self.i + 1 :].replace("''", "'"))
                        self.i = len(self.s)
                    else:
                        text.append(self.s[self.i + 1 : end].replace("''", "'"))
                        self.i = end + 1
                else:
                    text.append("'")
                    self.i += 1
            elif c == "{":
                if text:
                    nodes.append(Text("".join(text)))
                    text = []
                nodes.append(self.argument(depth))
            elif c == "}":
                break
            elif c == "#" and in_plural:
                if text:
                    nodes.append(Text("".join(text)))
                    text = []
                nodes.append(Pound())
                self.i += 1
            else:
                text.append(c)
                self.i += 1
        if text:
            nodes.append(Text("".join(text)))
        return tuple(nodes)

    def identifier(self) -> str:
        start = self.i
        while self.i < len(self.s) and (self.s[self.i].isalnum() or self.s[self.i] in "_-:=.+"):
            self.i += 1
        if start == self.i:
            raise self.fail("identifier expected")
        return self.s[start : self.i]

    def expect(self, char: str) -> None:
        self.ws()
        if self.i >= len(self.s) or self.s[self.i] != char:
            raise self.fail(f"{char!r} expected")
        self.i += 1

    def argument(self, depth: int) -> Arg:
        self.expect("{")
        self.ws()
        name = self.identifier()
        self.ws()
        if self.s[self.i : self.i + 1] == "}":
            self.i += 1
            return Arg(name, "simple")
        self.expect(",")
        self.ws()
        kind = self.identifier()
        self.ws()
        if kind in ("number", "date", "time"):
            style = None
            if self.s[self.i : self.i + 1] == ",":
                self.i += 1
                self.ws()
                style = self.identifier()
            self.expect("}")
            return Arg(name, "number" if kind == "number" else kind, style)
        if kind not in ("plural", "selectordinal", "select"):
            raise self.fail(f"unsupported argument type {kind!r}")
        self.expect(",")
        self.ws()
        offset = 0
        if self.s.startswith("offset:", self.i):
            self.i += len("offset:")
            self.ws()
            start = self.i
            while self.i < len(self.s) and self.s[self.i].isdigit():
                self.i += 1
            offset = int(self.s[start : self.i] or "0")
        options: list[tuple[str, tuple[Node, ...]]] = []
        while True:
            self.ws()
            if self.s[self.i : self.i + 1] == "}":
                self.i += 1
                break
            selector = self.identifier()
            self.expect("{")
            body = self.message(in_plural=kind != "select", depth=depth + 1)
            if self.s[self.i : self.i + 1] != "}":
                raise self.fail("'}' expected after option")
            self.i += 1
            options.append((selector, body))
        if not any(selector == "other" for selector, _ in options):
            raise MessageSyntaxError(f"{kind} argument {name!r} needs an 'other' option")
        return Arg(name, kind, None, offset, tuple(options))


@lru_cache(maxsize=4096)
def parse(source: str) -> tuple[Node, ...]:
    parser = _Parser(source)
    nodes = parser.message(in_plural=False)
    if parser.i != len(source):
        raise parser.fail("unbalanced '}'")
    return nodes


@lru_cache(maxsize=64)
def _locale(code: str) -> Locale:
    try:
        return Locale.parse(code.replace("-", "_"))
    except (UnknownLocaleError, ValueError):
        return Locale.parse("en")


@lru_cache(maxsize=64)
def _ordinal(code: str) -> PluralRule:
    locale = _locale(code)
    return locale.ordinal_form


def _number(value: Any, code: str, style: str | None = None) -> str:
    locale = _locale(code)
    try:
        if style == "percent":
            return str(format_percent(value, locale=locale))
        if style == "integer":
            return str(format_decimal(round(float(value)), locale=locale))
        return str(format_decimal(value, locale=locale))
    except (TypeError, ValueError, ArithmeticError):
        return str(value)


def arguments_of(nodes: tuple[Node, ...]) -> set[str]:
    names: set[str] = set()
    for node in nodes:
        if isinstance(node, Arg):
            names.add(node.name)
            for _, body in node.options:
                names |= arguments_of(body)
    return names


def render(source: str | tuple[Node, ...], args: Mapping[str, Any], locale: str) -> str:
    nodes = parse(source) if isinstance(source, str) else source
    return _render(nodes, args, locale, None)


def _render(nodes: tuple[Node, ...], args: Mapping[str, Any], code: str, pound: str | None) -> str:
    out: list[str] = []
    for node in nodes:
        if isinstance(node, Text):
            out.append(node.value)
        elif isinstance(node, Pound):
            out.append(pound if pound is not None else "#")
        else:
            out.append(_argument(node, args, code))
    return "".join(out)


def _argument(node: Arg, args: Mapping[str, Any], code: str) -> str:
    if node.name not in args:
        return "{" + node.name + "}"
    value = args[node.name]
    if node.kind == "simple":
        return (
            _number(value, code)
            if isinstance(value, int | float) and not isinstance(value, bool)
            else str(value)
        )
    if node.kind == "number":
        return _number(value, code, node.style)
    if node.kind in ("date", "time"):
        return str(value)
    options = dict(node.options)
    if node.kind == "select":
        return _render(options.get(str(value), options["other"]), args, code, None)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return _render(options["other"], args, code, str(value))
    exact = f"={int(number)}" if number == int(number) else None
    shown = number - node.offset
    pound = _number(int(shown) if shown == int(shown) else shown, code)
    if exact and exact in options:
        return _render(options[exact], args, code, pound)
    rule = _ordinal(code) if node.kind == "selectordinal" else _locale(code).plural_form
    category = rule(int(shown) if shown == int(shown) else shown)
    return _render(options.get(category, options["other"]), args, code, pound)
