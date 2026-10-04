import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../../api/client";
import type { Instance } from "../api";
import { COLUMNS, type Item, move, resize } from "../grid/engine";

/**
 * Edit session of the desktop arrangement (spec 027 T075, R13, FR-042): entering edit mode snapshots the
 * arrangement; drags, resizes and keyboard steps change a local draft through the shared engine (the
 * preview is exactly what the server will store); Save sends one ``PUT /dashboard/arrangement``; Cancel
 * restores the snapshot. Widgets added, hidden or removed meanwhile (immediate actions) are merged in.
 */
export type Cell = Pick<Item, "x" | "y" | "w" | "h">;

export const keyOf = (instance: Instance): string => instance.id ?? instance.widget_key;

function cellsOf(instances: readonly Instance[]): Map<string, Cell> {
  return new Map(
    instances.filter((i) => i.status === "active").map((i) => [keyOf(i), { x: i.x, y: i.y, w: i.w, h: i.h }]),
  );
}

function merge(previous: Map<string, Cell>, instances: readonly Instance[]): Map<string, Cell> {
  const fresh = cellsOf(instances);
  return new Map([...fresh].map(([key, cell]) => [key, previous.get(key) ?? cell]));
}

export function itemsOf(cells: Map<string, Cell>, instances: readonly Instance[]): Item[] {
  const byKey = new Map(instances.map((i) => [keyOf(i), i]));
  return [...cells].map(([key, cell]) => {
    const instance = byKey.get(key);
    const widget = instance?.widget;
    return {
      id: key,
      ...cell,
      min: widget ? { w: widget.min_w, h: widget.min_h } : undefined,
      max: widget ? { w: widget.max_w, h: widget.max_h } : undefined,
      locked: Boolean(instance?.locked),
    };
  });
}

export function useEditSession(
  instances: readonly Instance[],
  version: number | undefined,
  onSaved: () => void,
) {
  const [snapshot, setSnapshot] = useState<Map<string, Cell> | null>(null);
  const [draft, setDraft] = useState<Map<string, Cell> | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const instancesRef = useRef(instances);
  instancesRef.current = instances;

  const active = snapshot !== null;
  useEffect(() => {
    if (!active) return;
    // widgets added, hidden or removed during the session (immediate actions) join or leave the draft
    setDraft((current) => (current ? merge(current, instances) : current));
    setSnapshot((current) => (current ? merge(current, instances) : current));
  }, [instances, active]);

  const start = useCallback(() => {
    const cells = cellsOf(instancesRef.current);
    setSnapshot(cells);
    setDraft(cells);
    setError(null);
  }, []);

  const apply = useCallback((change: (items: Item[]) => Item[]) => {
    setDraft((current) => {
      if (!current) return current;
      const next = change(itemsOf(current, instancesRef.current));
      return new Map(next.map((item) => [item.id, { x: item.x, y: item.y, w: item.w, h: item.h }]));
    });
  }, []);

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
        ...(version !== undefined ? { headers: { "If-Match": String(version) } } : {}),
      });
    },
    [version],
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
    draft,
    dirty,
    saving,
    error,
    start,
    move: (key: string, x: number, y: number) => apply((items) => move(items, key, { x, y })),
    resize: (key: string, w: number, h: number) => apply((items) => resize(items, key, { w, h })),
    preview: (key: string, to: Partial<Cell>): Item[] | null => {
      if (!draft) return null;
      const items = itemsOf(draft, instancesRef.current);
      const target = items.find((i) => i.id === key);
      if (!target) return items;
      return to.w !== undefined || to.h !== undefined
        ? resize(items, key, { w: to.w ?? target.w, h: to.h ?? target.h })
        : move(items, key, { x: to.x ?? target.x, y: to.y ?? target.y });
    },
    save: () => finish(draft, dirty),
    cancel: () => finish(null, false), // the draft was never sent: the server still holds the snapshot
    columns: COLUMNS,
  };
}
