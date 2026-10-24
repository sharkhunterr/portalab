/**
 * Dashboard arrangement engine (spec 027 R10/R11): pure, deterministic functions over a grid of 12
 * (desktop), 8 (tablet) or 4 (phone) columns. The same algorithm lives in
 * ``backend/src/portalab/modules/dashboard/arrangement.py``; both read the shared cases of
 * ``tests/fixtures/dashboard-arrangements.json`` so the editor's preview is exactly what the server stores.
 *
 * - widgets never overlap; a moved or resized widget stays exactly where it was put (gaps are kept) and
 *   widgets in its way are pushed down;
 * - « auto fit » packs everything up and to the start and widens widgets into the space beside them;
 * - locked widgets never move;
 * - reading order (row, then column) is the DOM order and the order of derived views.
 */
export const COLUMNS = 12;
export type View = "desktop" | "tablet" | "phone";
export const VIEW_COLUMNS: Record<View, number> = { desktop: 12, tablet: 8, phone: 4 };

export interface Size {
  w: number;
  h: number;
}

export interface Item {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  min?: Size | undefined;
  max?: Size | undefined;
  locked?: boolean | undefined;
}

function clamp(value: number, low: number, high: number): number {
  return Math.max(low, Math.min(high, value));
}

export function collides(a: Item, b: Item): boolean {
  return a.id !== b.id && a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
}

function hits(item: Item, placed: readonly Item[]): Item[] {
  return placed.filter((other) => collides(item, other));
}

export function readingOrder(items: readonly Item[]): Item[] {
  return [...items].sort((a, b) => a.y - b.y || a.x - b.x || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
}

/** Clamp sizes to the widget's limits and the grid, and positions inside the grid. */
export function bound(item: Item, columns = COLUMNS): Item {
  const min = item.min ?? { w: 1, h: 1 };
  const max = item.max ?? { w: columns, h: 12 };
  const w = clamp(Math.round(item.w), Math.max(1, min.w), Math.min(columns, max.w));
  const h = clamp(Math.round(item.h), Math.max(1, min.h), Math.max(1, max.h));
  return { ...item, w, h, x: clamp(Math.round(item.x), 0, columns - w), y: Math.max(0, Math.round(item.y)) };
}

/** Pushes ``item`` down until it overlaps nothing in ``placed``. */
function settle(item: Item, placed: readonly Item[]): Item {
  let current = item;
  for (let colliding = hits(current, placed); colliding.length; colliding = hits(current, placed)) {
    current = { ...current, y: Math.max(...colliding.map((c) => c.y + c.h)) };
  }
  return current;
}

/** Vertical compaction: locked widgets stay; the others, in reading order, float up while free. */
export function compact(items: readonly Item[]): Item[] {
  const placed: Item[] = items.filter((i) => i.locked);
  for (const item of readingOrder(items.filter((i) => !i.locked))) {
    let current = settle(item, placed);
    while (current.y > 0 && hits({ ...current, y: current.y - 1 }, placed).length === 0) {
      current = { ...current, y: current.y - 1 };
    }
    placed.push(current);
  }
  return readingOrder(placed);
}

/** The ``others`` keep their place unless something sits there: then they move down (cascading). */
function push(fixed: Item[], others: readonly Item[]): Item[] {
  const pushed: Item[] = [];
  for (const item of readingOrder(others)) pushed.push(settle(item, [...fixed, ...pushed]));
  return readingOrder([...fixed, ...pushed]);
}

/** Place ``id`` at ``to`` (bounded) — it stays there; widgets in its way are pushed down. */
export function move(
  items: readonly Item[],
  id: string,
  to: { x: number; y: number },
  columns = COLUMNS,
): Item[] {
  const target = items.find((i) => i.id === id);
  if (!target || target.locked) return readingOrder(items);
  const moved = bound({ ...target, ...to }, columns);
  const locked = items.filter((i) => i.locked && i.id !== id);
  return push(
    [settle(moved, locked), ...locked],
    items.filter((i) => i.id !== id && !i.locked),
  );
}

/** Resize ``id`` (bounded by its limits and the grid) and make room for it. */
export function resize(items: readonly Item[], id: string, size: Size, columns = COLUMNS): Item[] {
  const target = items.find((i) => i.id === id);
  if (!target || target.locked) return readingOrder(items);
  const sized = bound({ ...target, ...size }, columns);
  return move(
    items.map((i) => (i.id === id ? sized : i)),
    id,
    { x: sized.x, y: sized.y },
    columns,
  );
}

/** « Auto fit »: everything floats up, then to the start of its row, then widens into the free space. */
export function autofit(items: readonly Item[], columns = COLUMNS): Item[] {
  const placed = compact(normalize(items, columns));
  let out: Item[] = placed.filter((i) => i.locked);
  for (const item of readingOrder(placed.filter((i) => !i.locked))) {
    let current = item;
    while (current.x > 0 && hits({ ...current, x: current.x - 1 }, out).length === 0) {
      current = { ...current, x: current.x - 1 };
    }
    out.push(current);
  }
  const grown: Item[] = [];
  for (const item of readingOrder(out)) {
    let current = item;
    const high = item.max?.w ?? columns;
    const others = out.filter((o) => o.id !== item.id);
    while (
      !current.locked &&
      current.x + current.w < columns &&
      current.w < high &&
      hits({ ...current, w: current.w + 1 }, [...others, ...grown]).length === 0
    ) {
      current = { ...current, w: current.w + 1 };
    }
    grown.push(current);
    out = out.map((o) => (o.id === current.id ? current : o));
  }
  return compact(grown);
}

/** The first position (top to bottom, start to end) where a ``w``×``h`` widget fits. */
export function firstFree(items: readonly Item[], size: Size, columns = COLUMNS): { x: number; y: number } {
  const w = clamp(size.w, 1, columns);
  for (let y = 0; ; y += 1) {
    for (let x = 0; x + w <= columns; x += 1) {
      if (hits({ id: "\u0000", x, y, w, h: size.h }, items).length === 0) return { x, y };
    }
  }
}

/** Normalization: bound every widget and resolve overlaps in reading order (gaps are kept). */
export function normalize(items: readonly Item[], columns = COLUMNS): Item[] {
  const placed: Item[] = items.filter((i) => i.locked).map((i) => bound(i, columns));
  for (const item of readingOrder(items.filter((i) => !i.locked))) {
    placed.push(settle(bound(item, columns), placed));
  }
  return readingOrder(placed);
}

/** Row packing in a given order (migration of ordered dashboards, derived views). */
export function flow(items: readonly Item[], columns = COLUMNS): Item[] {
  let x = 0;
  let y = 0;
  let row = 0;
  return items.map((item) => {
    const w = Math.min(item.w, columns);
    if (x + w > columns) {
      x = 0;
      y += row;
      row = 0;
    }
    const placed = { ...item, x, y, w };
    x += w;
    row = Math.max(row, item.h);
    return placed;
  });
}

/** Width of a desktop widget in a narrower view (R11): half or full width, never in-between slivers. */
export function derivedWidth(w: number, columns: number): number {
  if (columns >= COLUMNS) return w;
  if (columns <= 1) return 1;
  const threshold = columns <= 4 ? 3 : 6;
  return w <= threshold ? columns / 2 : columns;
}

/** Tablet (8 columns) / phone (4 columns) view of the desktop arrangement (one layout for every screen). */
export function derive(items: readonly Item[], columns: number): Item[] {
  return flow(
    readingOrder(items).map((item) => ({ ...item, w: derivedWidth(item.w, columns) })),
    columns,
  );
}

/** Issue 235: the arrangement cut into bands — runs of rows no widget crosses — in reading order. */
export function bands(items: readonly Item[]): Item[][] {
  const out: Item[][] = [];
  let band: Item[] = [];
  let bottom = 0;
  for (const item of readingOrder(items)) {
    if (band.length && item.y >= bottom) {
      out.push(band);
      band = [];
    }
    band.push(item);
    bottom = Math.max(bottom, item.y + item.h);
  }
  if (band.length) out.push(band);
  return out;
}

/**
 * Issue 235: on a wide screen, the desktop arrangement side by side in ``lanes`` columns of ``columns`` each —
 * every band keeps its widgets exactly as arranged and goes, in reading order, under the shortest lane.
 * Display only; the order returned is the bands' (one after the other), so reading order stays the member's.
 */
export function spread(items: readonly Item[], lanes: number, columns = COLUMNS): Item[] {
  const heights = Array.from({ length: Math.max(1, lanes) }, () => 0);
  const out: Item[] = [];
  for (const band of bands(items)) {
    const top = Math.min(...band.map((item) => item.y));
    const lane = heights.indexOf(Math.min(...heights));
    const start = heights[lane] ?? 0;
    for (const item of band) out.push({ ...item, x: item.x + lane * columns, y: item.y - top + start });
    heights[lane] = start + Math.max(...band.map((item) => item.y + item.h)) - top;
  }
  return out;
}
