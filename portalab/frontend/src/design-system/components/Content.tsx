import type { HTMLAttributes, ReactNode } from "react";
import { FunctionalState } from "../state/FunctionalState";
import type { FunctionalStateName } from "../state/stateMap";

/**
 * Content components (spec 022 T038): Card, Panel, Badge, Progress, Timeline, Avatar and an EntityCard
 * shared by media/service/user/achievement/project cards. Each renders its functional state through
 * ``FunctionalState`` (never color alone). Calendar and Chart wrappers ship with their first consumers
 * (011 calendar, 017 statistics).
 */
export function Card({
  title,
  children,
  className,
  ...props
}: HTMLAttributes<HTMLElement> & { title?: string }) {
  return (
    <article className={["ds-card", "ds-reflow", className].filter(Boolean).join(" ")} {...props}>
      {title ? <h3>{title}</h3> : null}
      {children}
    </article>
  );
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
  return (
    <div className="ds-field">
      <span>{label}</span>
      {value === null ? (
        <progress className="ds-progress" aria-label={label} />
      ) : (
        <progress className="ds-progress" aria-label={label} value={value} max={max}>
          {Math.round((value / max) * 100)}%
        </progress>
      )}
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

export function Avatar({ name, src }: { name: string; src?: string }) {
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
  return (
    <span className="ds-avatar" role="img" aria-label={name}>
      {src ? (
        <img src={src} alt="" width={40} height={40} />
      ) : (
        <span aria-hidden="true">{initials || "?"}</span>
      )}
    </span>
  );
}

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
