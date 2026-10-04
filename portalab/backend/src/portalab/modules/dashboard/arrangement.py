"""Dashboard arrangement engine (spec 027 R10/R11, T070) — the server twin of the editor's ``engine.ts``.

Pure, deterministic functions over a 12-column grid: widgets never overlap, float up into free space
(vertical compaction), a moved/resized widget pushes the ones in its way down, locked widgets never move,
and reading order (row, then column) is the stored ``position``. Both implementations read the shared
cases of ``tests/fixtures/dashboard-arrangements.json`` so the editor's preview is what the server stores.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace

COLUMNS = 12
MAX_ROWS_SIZE = 12


@dataclass(frozen=True, slots=True)
class Size:
    w: int
    h: int


@dataclass(frozen=True, slots=True)
class Item:
    id: str
    x: int
    y: int
    w: int
    h: int
    min: Size | None = None
    max: Size | None = None
    locked: bool = False


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def collides(a: Item, b: Item) -> bool:
    return a.id != b.id and a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h


def _hits(item: Item, placed: Iterable[Item]) -> list[Item]:
    return [other for other in placed if collides(item, other)]


def reading_order(items: Iterable[Item]) -> list[Item]:
    return sorted(items, key=lambda i: (i.y, i.x, i.id))


def bound(item: Item, columns: int = COLUMNS) -> Item:
    """Clamp sizes to the widget's limits and the grid, and positions inside the grid."""
    low = item.min or Size(1, 1)
    high = item.max or Size(columns, MAX_ROWS_SIZE)
    w = _clamp(round(item.w), max(1, low.w), min(columns, high.w))
    h = _clamp(round(item.h), max(1, low.h), max(1, high.h))
    return replace(item, w=w, h=h, x=_clamp(round(item.x), 0, columns - w), y=max(0, round(item.y)))


def _settle(item: Item, placed: Sequence[Item]) -> Item:
    current = item
    while colliding := _hits(current, placed):
        current = replace(current, y=max(c.y + c.h for c in colliding))
    return current


def compact(items: Iterable[Item]) -> list[Item]:
    """Locked widgets stay; the others, in reading order, float up while free."""
    items = list(items)
    placed = [i for i in items if i.locked]
    for item in reading_order(i for i in items if not i.locked):
        current = _settle(item, placed)
        while current.y > 0 and not _hits(replace(current, y=current.y - 1), placed):
            current = replace(current, y=current.y - 1)
        placed.append(current)
    return reading_order(placed)


def move(items: Sequence[Item], id: str, x: int, y: int, columns: int = COLUMNS) -> list[Item]:
    target = next((i for i in items if i.id == id), None)
    if target is None or target.locked:
        return compact(items)
    moved = bound(replace(target, x=x, y=y), columns)
    locked = [i for i in items if i.locked and i.id != id]
    fixed = [_settle(moved, locked), *locked]
    pushed: list[Item] = []
    for item in reading_order(i for i in items if i.id != id and not i.locked):
        pushed.append(_settle(item, [*fixed, *pushed]))
    return compact([*fixed, *pushed])


def resize(items: Sequence[Item], id: str, w: int, h: int, columns: int = COLUMNS) -> list[Item]:
    target = next((i for i in items if i.id == id), None)
    if target is None or target.locked:
        return compact(items)
    sized = bound(replace(target, w=w, h=h), columns)
    return move([sized if i.id == id else i for i in items], id, sized.x, sized.y, columns)


def first_free(items: Sequence[Item], w: int, h: int, columns: int = COLUMNS) -> tuple[int, int]:
    w = _clamp(w, 1, columns)
    y = 0
    while True:
        for x in range(columns - w + 1):
            if not _hits(Item("\0", x, y, w, h), items):
                return x, y
        y += 1


def normalize(items: Iterable[Item], columns: int = COLUMNS) -> list[Item]:
    """Server-side: bound every widget, resolve overlaps in reading order, compact."""
    items = list(items)
    placed = [bound(i, columns) for i in items if i.locked]
    for item in reading_order(i for i in items if not i.locked):
        placed.append(_settle(bound(item, columns), placed))
    return compact(placed)


def flow(items: Iterable[Item], columns: int = COLUMNS) -> list[Item]:
    """Row packing in the given order (migration of ordered dashboards, derived views)."""
    x = y = row = 0
    out: list[Item] = []
    for item in items:
        w = min(item.w, columns)
        if x + w > columns:
            x, y, row = 0, y + row, 0
        out.append(replace(item, x=x, y=y, w=w))
        x += w
        row = max(row, item.h)
    return out


def derived_width(w: int, columns: int) -> int:
    if columns >= COLUMNS:
        return w
    if columns <= 1:
        return 1
    threshold = 3 if columns == 2 else 6
    return columns // 2 if w <= threshold else columns


def derive(items: Iterable[Item], columns: int) -> list[Item]:
    """Tablet/phone view of the desktop arrangement — computed, never stored."""
    return flow([replace(i, w=derived_width(i.w, columns)) for i in reading_order(items)], columns)
