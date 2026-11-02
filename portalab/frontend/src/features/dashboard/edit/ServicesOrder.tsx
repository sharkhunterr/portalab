import { type PointerEvent, useRef, useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { CONNECTOR_ICON } from "../../services/connectorIcons";
import "./services-order.css";

export interface OrderedService {
  id: string;
  name: string;
  connector?: string | null;
  state?: string | null;
}

const TONES: Record<string, string> = {
  operational: "ok",
  degraded: "warn",
  unavailable: "bad",
  maintenance: "info",
};

/**
 * issue 333: the services a widget shows, in its order — each one ticked or not, moved by its grip (mouse
 * or finger) or by its arrows (keyboard). Nothing chosen (``[]``): every service, in the usual order — so a
 * service added later shows up until a choice is made.
 */
export function ServicesOrder({
  label,
  value,
  services,
  onChange,
}: {
  label: string;
  value: string[];
  services: OrderedService[];
  onChange: (next: string[]) => void;
}) {
  const t = useT();
  const all = services.map((s) => s.id);
  const known = new Set(all);
  const chosen = value.length ? value.filter((id) => known.has(id)) : all;
  const shown = new Set(chosen);
  // the chosen ones in their order, then the others
  const order = [...chosen, ...all.filter((id) => !shown.has(id))];
  const byId = new Map(services.map((s) => [s.id, s]));
  const rows = useRef<Map<string, HTMLLIElement>>(new Map());
  const [dragging, setDragging] = useState<string | null>(null);

  // the choice saved: « every service, as usual » when it is just that
  const save = (ids: string[]) =>
    onChange(ids.length === all.length && ids.every((id, i) => id === all[i]) ? [] : ids);
  const move = (id: string, to: number) => {
    const next = chosen.filter((x) => x !== id);
    next.splice(Math.max(0, Math.min(to, next.length)), 0, id);
    save(next);
  };
  const toggle = (id: string, on: boolean) => {
    if (on) save([...chosen, id]);
    else if (chosen.length > 1) save(chosen.filter((x) => x !== id));
  };
  const drag = (id: string) => (event: PointerEvent<HTMLButtonElement>) => {
    if (!shown.has(id)) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragging(id);
  };
  const follow = (event: PointerEvent<HTMLButtonElement>) => {
    if (!dragging) return;
    // the row under the pointer takes its place
    const index = chosen.findIndex((id) => {
      const box = rows.current.get(id)?.getBoundingClientRect();
      return box ? event.clientY < box.top + box.height / 2 : false;
    });
    const from = chosen.indexOf(dragging);
    // where it goes among the others: before that row (or last, below them all)
    const target = index === -1 ? chosen.length - 1 : index > from ? index - 1 : index;
    if (target !== from) move(dragging, target);
  };
  const drop = () => setDragging(null);

  return (
    <fieldset className="services-order">
      <legend>{label}</legend>
      <p className="services-order__hint">{t("dashboard:servicesOrder.hint")}</p>
      <ol className="services-order__list">
        {order.map((id) => {
          const service = byId.get(id);
          if (!service) return null;
          const on = shown.has(id);
          const at = chosen.indexOf(id);
          return (
            <li
              key={id}
              ref={(node) => {
                if (node) rows.current.set(id, node);
                else rows.current.delete(id);
              }}
              className="services-order__row"
              data-off={on ? undefined : ""}
              data-dragging={dragging === id ? "" : undefined}
            >
              <button
                type="button"
                className="services-order__grip"
                aria-label={t("dashboard:servicesOrder.drag", { name: service.name })}
                disabled={!on}
                onPointerDown={drag(id)}
                onPointerMove={follow}
                onPointerUp={drop}
                onPointerCancel={drop}
              >
                <Icon name="grip" size={16} />
              </button>
              <label className="services-order__name">
                <input
                  type="checkbox"
                  checked={on}
                  disabled={on && chosen.length === 1}
                  onChange={(e) => toggle(id, e.target.checked)}
                />
                <span
                  className="services-order__icon has-tone"
                  data-tone={TONES[service.state ?? ""] ?? "neutral"}
                  aria-hidden="true"
                >
                  <Icon name={CONNECTOR_ICON[service.connector ?? ""] ?? "server"} size={14} />
                </span>
                {service.name}
              </label>
              {on ? (
                <span className="services-order__moves">
                  <Button
                    variant="ghost"
                    size="icon"
                    disabled={at === 0}
                    aria-label={t("dashboard:servicesOrder.up", { name: service.name })}
                    onClick={() => move(id, at - 1)}
                  >
                    <Icon name="arrow-up" size={14} />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    disabled={at === chosen.length - 1}
                    aria-label={t("dashboard:servicesOrder.down", { name: service.name })}
                    onClick={() => move(id, at + 1)}
                  >
                    <Icon name="arrow-down" size={14} />
                  </Button>
                </span>
              ) : null}
            </li>
          );
        })}
      </ol>
      {value.length ? (
        <Button variant="ghost" onClick={() => onChange([])}>
          <Icon name="undo" size={14} />
          {t("dashboard:servicesOrder.all")}
        </Button>
      ) : null}
    </fieldset>
  );
}
