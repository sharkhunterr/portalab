import type { HTMLAttributes, ReactNode } from "react";
import { FunctionalState } from "../state/FunctionalState";
import type { FunctionalStateName } from "../state/stateMap";
import { Icon } from "./Icon";

/**
 * Content components (spec 022 T038): Card, Panel, Badge, Progress, Timeline, Avatar and an EntityCard
 * shared by media/service/user/achievement/project cards. Each renders its functional state through
 * ``FunctionalState`` (never color alone). Calendar and Chart wrappers ship with their first consumers
 * (011 calendar, 017 statistics).
 */
export function Card({
  title,
  icon,
  actions,
  variant,
  level = 3,
  children,
  className,
  ...props
}: HTMLAttributes<HTMLElement> & {
  title?: string;
  /** Heading level of the title, to keep the page outline (default 3). */
  level?: 2 | 3 | 4;
  icon?: string;
  actions?: ReactNode;
  /** Defaults to the theme's card style (027 ``data-cards``). */
  variant?: "elevated" | "flat" | "outlined" | "glass";
}) {
  return (
    <article
      className={["ds-card", "ds-reflow", className].filter(Boolean).join(" ")}
      data-variant={variant}
      {...props}
    >
      {title || actions ? (
        <header className="ds-card__header">
          {title ? (
            <Heading level={level} className="ds-card__title">
              {icon ? <Icon name={icon} size={18} /> : null}
              {title}
            </Heading>
          ) : null}
          {actions ? <div className="ds-card__actions">{actions}</div> : null}
        </header>
      ) : null}
      {children}
    </article>
  );
}

function Heading({ level, ...props }: HTMLAttributes<HTMLHeadingElement> & { level: 2 | 3 | 4 }) {
  const Tag = `h${level}` as const;
  return <Tag {...props} />;
}

export function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="ds-panel ds-reflow" aria-label={title}>
      <h3>{title}</h3>
      {children}
    </section>
  );
}

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | FunctionalStateName;
}) {
  return (
    <span className={`ds-badge${tone === "neutral" ? "" : ` functional-state--${tone}`}`} data-tone={tone}>
      {children}
    </span>
  );
}

export function Progress({ value, max = 100, label }: { value: number | null; max?: number; label: string }) {
  const percent = value === null ? null : Math.round((Math.min(value, max) / Math.max(max, 1)) * 100);
  return (
    <div className="ds-progress-field">
      <span className="ds-progress-field__label">{label}</span>
      <span
        className="ds-bar ds-bar--accent"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        {...(percent === null ? { "data-indeterminate": "true" } : { "aria-valuenow": percent })}
      >
        <span className="ds-bar__fill" style={{ inlineSize: percent === null ? "35%" : `${percent}%` }} />
      </span>
    </div>
  );
}

export interface TimelineEntry {
  id: string;
  at: string;
  title: string;
  detail?: ReactNode;
}

export function Timeline({ entries, label }: { entries: TimelineEntry[]; label: string }) {
  return (
    <ol className="ds-timeline" aria-label={label}>
      {entries.map((entry) => (
        <li key={entry.id} className="ds-timeline__item">
          <time dateTime={entry.at}>{entry.at}</time> — <strong>{entry.title}</strong>
          {entry.detail ? <div>{entry.detail}</div> : null}
        </li>
      ))}
    </ol>
  );
}

export { Avatar } from "./Avatar";

export interface EntityCardProps {
  kind: "media" | "service" | "user" | "achievement" | "project";
  title: string;
  subtitle?: string;
  state?: FunctionalStateName;
  stateLabel?: string;
  meta?: ReactNode;
  actions?: ReactNode;
}

export function EntityCard({ kind, title, subtitle, state, stateLabel, meta, actions }: EntityCardProps) {
  return (
    <article className="ds-card ds-reflow" data-kind={kind} aria-label={title}>
      <h3>{title}</h3>
      {subtitle ? <p>{subtitle}</p> : null}
      {state ? <FunctionalState state={state} label={stateLabel} /> : null}
      {meta}
      {actions ? <div className="ds-stack ds-stack--row">{actions}</div> : null}
    </article>
  );
}
