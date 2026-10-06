import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../../api/client";
import type { Instance } from "../api";
import {
  autofit,
  COLUMNS,
  derive,
  type Item,
  move,
  normalize,
  resize,
  VIEW_COLUMNS,
  type View,
} from "../grid/engine";

/**
 * Edit session of an arrangement (spec 027 T075, R13, FR-042): entering edit mode snapshots the arrangement
 * of one screen (desktop, tablet or phone); drags, resizes, keyboard steps and « auto fit » change a local
 * draft through the shared engine (the preview is exactly what the server will store); Save sends one
 * ``PUT /dashboard/arrangement`` (with ``?view=`` for a tablet/phone arrangement); Cancel restores the
 * snapshot. Widgets added, hidden or removed meanwhile (immediate actions) are merged in.
 */
export type Cell = Pick<Item, "x" | "y" | "w" | "h">;
export type LayoutMode = "shared" | "per_device";

export const keyOf = (instance: Instance): string => instance.id ?? instance.widget_key;

function limits(instance: Instance | undefined, columns: number) {
  const widget = instance?.widget;
  if (!widget) return { min: undefined, max: undefined };
  return {
    min: { w: Math.min(widget.min_w, columns), h: widget.min_h },
    max: { w: Math.min(widget.max_w, columns), h: widget.max_h },
  };
}

export function itemsOf(cells: Map<string, Cell>, instances: readonly Instance[], columns = COLUMNS): Item[] {
  const byKey = new Map(instances.map((i) => [keyOf(i), i]));
  return [...cells].map(([key, cell]) => {
    const instance = byKey.get(key);
    return {
      id: key,
      ...cell,
      ...(columns === COLUMNS ? limits(instance, columns) : { min: undefined, max: undefined }),
      locked: Boolean(instance?.locked),
    };
  });
}

/**
 * The cells of one screen: the desktop coordinates; on tablet/phone the member's own arrangement when they
 * arrange each screen on its own (widgets not placed there yet derived), else derived from the desktop.
 */
export function cellsFor(instances: readonly Instance[], view: View, mode: LayoutMode): Map<string, Cell> {
  const active = instances.filter((i) => i.status === "active");
  const desktop = active.map((i) => ({ id: keyOf(i), x: i.x, y: i.y, w: i.w, h: i.h }));
  if (view === "desktop") return new Map(desktop.map(({ id, ...cell }) => [id, cell]));
  const columns = VIEW_COLUMNS[view];
  const derived = new Map(derive(desktop, columns).map(({ id, x, y, w, h }) => [id, { x, y, w, h }]));
  if (mode === "shared") return derived;
  const own = active.map((i) => {
    const stored = (i.views as Record<string, Cell> | undefined)?.[view];
    const cell = stored ?? derived.get(keyOf(i)) ?? { x: 0, y: 0, w: columns, h: i.h };
    return { id: keyOf(i), ...cell };
  });
  return new Map(normalize(own, columns).map(({ id, x, y, w, h }) => [id, { x, y, w, h }]));
}

/** The draft with widgets added or removed meanwhile — the same map when nothing changed (no re-render). */
function merge(previous: Map<string, Cell>, fresh: Map<string, Cell>): Map<string, Cell> {
  if (previous.size === fresh.size && [...fresh.keys()].every((key) => previous.has(key))) return previous;
  return new Map([...fresh].map(([key, cell]) => [key, previous.get(key) ?? cell]));
}

export function useEditSession(
  instances: readonly Instance[],
  version: number | undefined,
  mode: LayoutMode,
  onSaved: () => void,
) {
  const [view, setView] = useState<View>("desktop");
  const [snapshot, setSnapshot] = useState<Map<string, Cell> | null>(null);
  const [draft, setDraft] = useState<Map<string, Cell> | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const instancesRef = useRef(instances);
  instancesRef.current = instances;
  const columns = VIEW_COLUMNS[view];

  const active = snapshot !== null;
  useEffect(() => {
    if (!active) return;
    // widgets added, hidden or removed during the session (immediate actions) join or leave the draft
    const fresh = cellsFor(instances, view, mode);
    setDraft((current) => (current ? merge(current, fresh) : current));
    setSnapshot((current) => (current ? merge(current, fresh) : current));
  }, [instances, active, view, mode]);

  const start = useCallback(
    (target: View = "desktop", fresh?: readonly Instance[], layout?: LayoutMode) => {
      const cells = cellsFor(fresh ?? instancesRef.current, target, layout ?? mode);
      setView(target);
      setSnapshot(cells);
      setDraft(cells);
      setError(null);
    },
    [mode],
  );

  const apply = useCallback(
    (change: (items: Item[]) => Item[]) => {
      setDraft((current) => {
        if (!current) return current;
        const next = change(itemsOf(current, instancesRef.current, columns));
        return new Map(next.map((item) => [item.id, { x: item.x, y: item.y, w: item.w, h: item.h }]));
      });
    },
    [columns],
  );

  const send = useCallback(
    async (cells: Map<string, Cell>) => {
      const byKey = new Map(instancesRef.current.map((i) => [keyOf(i), i]));
      const items = [...cells]
        .filter(([key]) => byKey.has(key))
        .map(([key, cell]) => {
          const instance = byKey.get(key) as Instance;
          return { id: instance.id ?? null, widget_key: instance.widget_key, ...cell };
        });
      await api.PUT("/api/v1/dashboard/arrangement", {
        body: { items },
        params: { query: { view } },
        ...(version !== undefined ? { headers: { "If-Match": String(version) } } : {}),
      });
    },
    [version, view],
  );

  const dirty = useMemo(() => {
    if (!snapshot || !draft) return false;
    return [...draft].some(([key, cell]) => {
      const before = snapshot.get(key);
      return (
        !before || before.x !== cell.x || before.y !== cell.y || before.w !== cell.w || before.h !== cell.h
      );
    });
  }, [snapshot, draft]);

  const finish = useCallback(
    async (cells: Map<string, Cell> | null, changed: boolean) => {
      setSaving(true);
      try {
        if (cells && changed) await send(cells);
        setSnapshot(null);
        setDraft(null);
        onSaved();
      } catch (failure) {
        setError(failure);
      } finally {
        setSaving(false);
      }
    },
    [send, onSaved],
  );

  return {
    editing: snapshot !== null,
    view,
    columns,
    draft,
    dirty,
    saving,
    error,
    start,
    move: (key: string, x: number, y: number) => apply((items) => move(items, key, { x, y }, columns)),
    resize: (key: string, w: number, h: number) => apply((items) => resize(items, key, { w, h }, columns)),
    autofit: () => apply((items) => autofit(items, columns)),
    preview: (key: string, to: Partial<Cell>): Item[] | null => {
      if (!draft) return null;
      const items = itemsOf(draft, instancesRef.current, columns);
      const target = items.find((i) => i.id === key);
      if (!target) return items;
      return to.w !== undefined || to.h !== undefined
        ? resize(items, key, { w: to.w ?? target.w, h: to.h ?? target.h }, columns)
        : move(items, key, { x: to.x ?? target.x, y: to.y ?? target.y }, columns);
    },
    save: () => finish(draft, dirty),
    cancel: () => finish(null, false), // the draft was never sent: the server still holds the snapshot
  };
}
