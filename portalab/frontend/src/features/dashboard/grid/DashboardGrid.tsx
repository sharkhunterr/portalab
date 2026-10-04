import { type KeyboardEvent, type PointerEvent, type ReactNode, useRef, useState } from "react";
import { useAnnounce } from "../../../design-system/a11y/Announce";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import type { Instance } from "../api";
import { type Cell, itemsOf, keyOf } from "../edit/EditSession";
import { derive, type Item, readingOrder } from "./engine";

/**
 * Dashboard grid (spec 027 T074/T076/T077): widgets at explicit grid coordinates on desktop (12 columns),
 * the derived arrangement on tablet (6) and phone (2) — computed, never stored. DOM order = reading order.
 * In desktop edit mode every widget gets a grip (drag with mouse, touch or pen; or Enter then arrow keys)
 * and a resize corner (drag; or Shift + arrow keys). The preview runs the shared engine, so neighbours make
 * room live exactly as the server will store it. Locked widgets show no handles.
 */
export interface Arranger {
  move: (key: string, x: number, y: number) => void;
  resize: (key: string, w: number, h: number) => void;
  preview: (key: string, to: Partial<Cell>) => Item[] | null;
}

interface DashboardGridProps {
  label: string;
  instances: readonly Instance[];
  cells: Map<string, Cell>;
  columns: number;
  arranger?: Arranger | null;
  render: (instance: Instance, handles: ReactNode) => ReactNode;
}

interface Drag {
  key: string;
  mode: "move" | "resize";
  startX: number;
  startY: number;
  origin: Cell;
  target: Cell;
}

function metrics(grid: HTMLElement, columns: number) {
  const rect = grid.getBoundingClientRect();
  const style = getComputedStyle(grid);
  const gap = Number.parseFloat(style.columnGap) || 0;
  const row = Number.parseFloat(style.gridAutoRows) || 72;
  return { colStep: (rect.width + gap) / columns, rowStep: row + (Number.parseFloat(style.rowGap) || 0) };
}

export function DashboardGrid({ label, instances, cells, columns, arranger, render }: DashboardGridProps) {
  const t = useT();
  const announce = useAnnounce();
  const grid = useRef<HTMLOListElement>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [grabbed, setGrabbed] = useState<string | null>(null);
  const byKey = new Map(instances.map((i) => [keyOf(i), i]));

  let placed: Item[] = itemsOf(cells, instances);
  if (drag && arranger) {
    placed =
      arranger.preview(
        drag.key,
        drag.mode === "move"
          ? { x: drag.target.x, y: drag.target.y }
          : { w: drag.target.w, h: drag.target.h },
      ) ?? placed;
  }
  const shown = columns >= 12 ? readingOrder(placed) : derive(placed, columns);
  const titleOf = (instance: Instance) =>
    instance.widget ? t(instance.widget.title_key) : instance.widget_key;

  const begin = (event: PointerEvent<HTMLElement>, key: string, mode: Drag["mode"]) => {
    const cell = cells.get(key);
    if (!cell || !grid.current) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    setDrag({ key, mode, startX: event.clientX, startY: event.clientY, origin: cell, target: cell });
  };
  const track = (event: PointerEvent<HTMLElement>) => {
    if (!drag || !grid.current) return;
    const { colStep, rowStep } = metrics(grid.current, columns);
    const dx = Math.round((event.clientX - drag.startX) / colStep);
    const dy = Math.round((event.clientY - drag.startY) / rowStep);
    const { origin } = drag;
    const target =
      drag.mode === "move"
        ? {
            ...origin,
            x: Math.max(0, Math.min(columns - origin.w, origin.x + dx)),
            y: Math.max(0, origin.y + dy),
          }
        : { ...origin, w: Math.max(1, origin.w + dx), h: Math.max(1, origin.h + dy) };
    if (
      target.x !== drag.target.x ||
      target.y !== drag.target.y ||
      target.w !== drag.target.w ||
      target.h !== drag.target.h
    ) {
      setDrag({ ...drag, target });
    }
  };
  const end = () => {
    if (!drag || !arranger) return;
    const { key, mode, target } = drag;
    setDrag(null);
    if (mode === "move") arranger.move(key, target.x, target.y);
    else arranger.resize(key, target.w, target.h);
    const instance = byKey.get(key);
    if (instance)
      announce(
        t(mode === "move" ? "dashboard:moved" : "dashboard:resized", {
          title: titleOf(instance),
          position: target.y + 1,
          w: target.w,
          h: target.h,
        }),
      );
  };

  const onKey = (event: KeyboardEvent<HTMLButtonElement>, key: string) => {
    const instance = byKey.get(key);
    const cell = cells.get(key);
    if (!arranger || !instance || !cell) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      const next = grabbed === key ? null : key;
      setGrabbed(next);
      announce(t(next ? "dashboard:grabbed" : "dashboard:dropped", { title: titleOf(instance) }));
      return;
    }
    if (event.key === "Escape") {
      setGrabbed(null);
      return;
    }
    if (grabbed !== key) return;
    const step: Record<string, [number, number]> = {
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
    };
    const delta = step[event.key];
    if (!delta) return;
    event.preventDefault();
    if (event.shiftKey) {
      arranger.resize(key, Math.max(1, cell.w + delta[0]), Math.max(1, cell.h + delta[1]));
      announce(
        t("dashboard:resized", { title: titleOf(instance), w: cell.w + delta[0], h: cell.h + delta[1] }),
      );
    } else {
      arranger.move(key, Math.max(0, cell.x + delta[0]), Math.max(0, cell.y + delta[1]));
      announce(t("dashboard:moved", { title: titleOf(instance), position: cell.y + delta[1] + 1 }));
    }
  };

  return (
    <div className="dashboard-grid-container">
      <ol
        ref={grid}
        className="dashboard-grid"
        aria-label={label}
        data-columns={columns}
        data-editing={arranger ? "true" : undefined}
        style={{ "--columns": columns } as React.CSSProperties}
      >
        {shown.map((item) => {
          const instance = byKey.get(item.id);
          if (!instance) return null;
          const dragging = drag?.key === item.id;
          const editable = Boolean(arranger) && !instance.locked;
          const handles = editable ? (
            <>
              <button
                type="button"
                className="dash-grip"
                aria-pressed={grabbed === item.id}
                aria-label={t("dashboard:arrange", { title: titleOf(instance) })}
                title={t("dashboard:arrangeHint")}
                onPointerDown={(event) => begin(event, item.id, "move")}
                onPointerMove={track}
                onPointerUp={end}
                onPointerCancel={() => setDrag(null)}
                onKeyDown={(event) => onKey(event, item.id)}
              >
                <Icon name="grip" size={18} />
              </button>
              <span
                className="dash-resize"
                aria-hidden="true"
                onPointerDown={(event) => begin(event, item.id, "resize")}
                onPointerMove={track}
                onPointerUp={end}
                onPointerCancel={() => setDrag(null)}
              />
            </>
          ) : null;
          return (
            <li
              key={item.id}
              className="dashboard-grid__cell"
              data-dragging={dragging ? "true" : undefined}
              data-grabbed={grabbed === item.id ? "true" : undefined}
              style={{
                gridColumn: `${item.x + 1} / span ${item.w}`,
                gridRow: `${item.y + 1} / span ${item.h}`,
              }}
            >
              {render(instance, handles)}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
