import type { ReactNode } from "react";
import { Link } from "react-router";
import { Icon } from "../../../../design-system/components/Icon";

export interface Kpi {
  key: string;
  icon: string;
  label: string;
  value: ReactNode;
  hint?: ReactNode | undefined;
  /** its colour: the accent by default, ``warn`` for something waiting, ``ok`` for money in */
  tone?: "accent" | "ok" | "warn" | "muted" | undefined;
  to?: string | undefined;
}

/**
 * #98 — figures at a glance, as compact tiles: an icon in a tinted circle, the figure, what it is, a line
 * of context. Two to a row on a phone, as many as fit on a wide screen; a tile may open its page.
 */
export function Kpis({ items, label }: { items: Kpi[]; label: string }) {
  return (
    <ul className="mk-kpis" aria-label={label}>
      {items.map((kpi) => {
        const body = (
          <>
            <span className="mk-kpi__icon" aria-hidden="true">
              <Icon name={kpi.icon} size={18} />
            </span>
            <span className="mk-kpi__text">
              <span className="mk-kpi__value">{kpi.value}</span>
              <span className="mk-kpi__label">{kpi.label}</span>
              {kpi.hint ? <span className="mk-kpi__hint">{kpi.hint}</span> : null}
            </span>
          </>
        );
        return (
          <li key={kpi.key} className="mk-kpi" data-tone={kpi.tone ?? "accent"}>
            {kpi.to ? (
              <Link to={kpi.to} className="mk-kpi__link">
                {body}
              </Link>
            ) : (
              <div className="mk-kpi__link">{body}</div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
