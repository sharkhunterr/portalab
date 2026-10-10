import { type ReactNode, useId } from "react";
import { Link } from "react-router";
import { Progress } from "../components/Content";
import { Icon } from "../components/Icon";
import { DialogActions, useInDialog } from "../components/Overlays";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/Placeholders";
import "./admin-kit.css";

/**
 * Administration kit (027 US10): every administration page is built from the same few blocks so they look
 * and behave alike on phone, tablet and desktop —
 *
 * * ``AdminPage``: the page header (icon tile, title, one-line purpose, primary/secondary actions), an
 *   optional sub-navigation and the content stack;
 * * ``AdminSection``: a titled card (description, actions on the right) — every block of a page is one;
 * * ``AdminStats``: a row of key figures, each with a tone;
 * * ``AdminTable``: a data table that becomes one card per row on narrow screens;
 * * ``StatusBadge``: the one status pill (dot + text, never color alone);
 * * ``AdminToolbar`` / ``SearchBox``: filters above a list; ``FormGrid`` / ``FormActions`` for forms;
 * * ``KeyValues``: label/value facts; ``AdminEmpty``: the empty state that always leads somewhere.
 */
export type Tone = "ok" | "warn" | "bad" | "info" | "neutral";

export function AdminPage({
  icon,
  title,
  description,
  primary,
  secondary,
  tabs,
  children,
  wide = false,
}: {
  icon: string;
  title: string;
  description?: ReactNode | undefined;
  primary?: ReactNode | undefined;
  secondary?: ReactNode | undefined;
  tabs?: ReactNode | undefined;
  children: ReactNode;
  wide?: boolean | undefined;
}) {
  const titleId = useId();
  return (
    <section className="admin-page" data-wide={wide || undefined} aria-labelledby={titleId}>
      <PageHeader
        titleId={titleId}
        level={2}
        icon={icon}
        title={title}
        context={description}
        primary={primary}
        secondary={secondary}
      />
      {tabs ? <div className="admin-page__tabs">{tabs}</div> : null}
      <div className="admin-page__body">{children}</div>
    </section>
  );
}

export interface AdminTab {
  key: string;
  label: string;
  count?: number | undefined;
  /** 061: still to unlock (in the shop): a lock beside the label; the tab stays reachable */
  locked?: boolean | undefined;
}

/** Sub-navigation of a page (state lives in the page): buttons with ``aria-pressed``. */
export function AdminTabs({
  tabs,
  current,
  onChange,
  label,
}: {
  tabs: AdminTab[];
  current: string;
  onChange: (key: string) => void;
  label: string;
}) {
  return (
    <fieldset className="ds-subnav admin-tabs" aria-label={label}>
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          aria-pressed={current === tab.key}
          onClick={() => onChange(tab.key)}
        >
          {tab.label}
          {tab.locked ? <Icon name="lock" size={13} className="admin-tabs__lock" /> : null}
          {tab.count !== undefined ? (
            <>
              {" "}
              <span className="admin-tabs__count">{tab.count}</span>
            </>
          ) : null}
        </button>
      ))}
    </fieldset>
  );
}

export function AdminSection({
  title,
  description,
  icon,
  actions,
  children,
  flush = false,
  span,
}: {
  title: string;
  description?: ReactNode | undefined;
  icon?: string | undefined;
  actions?: ReactNode | undefined;
  children: ReactNode;
  /** No inner padding (tables, lists that draw their own rows). */
  flush?: boolean | undefined;
  /** Columns taken in an ``AdminGrid`` (1 by default, "full" for the whole row). */
  span?: "full" | undefined;
}) {
  const headingId = useId();
  return (
    // a plain block (not a landmark): data regions inside already label themselves
    <div className="admin-section" data-span={span}>
      <header className="admin-section__header">
        <div className="admin-section__titles">
          <h3 id={headingId} className="admin-section__title">
            {icon ? <Icon name={icon} size={18} /> : null}
            {title}
          </h3>
          {description ? <p className="admin-section__description">{description}</p> : null}
        </div>
        {actions ? <div className="admin-section__actions">{actions}</div> : null}
      </header>
      <div className="admin-section__body" data-flush={flush || undefined}>
        {children}
      </div>
    </div>
  );
}

/** Two columns of sections on wide screens, one on phones. */
export function AdminGrid({ children }: { children: ReactNode }) {
  return <div className="admin-grid">{children}</div>;
}

export interface Stat {
  key: string;
  label: string;
  value: ReactNode;
  hint?: ReactNode | undefined;
  tone?: Tone | undefined;
  icon?: string | undefined;
  to?: string | undefined;
}

export function AdminStats({ stats, label }: { stats: Stat[]; label: string }) {
  return (
    <ul className="admin-stats" aria-label={label}>
      {stats.map((stat) => {
        const body = (
          <>
            <span className="admin-stat__label">
              {stat.icon ? <Icon name={stat.icon} size={16} /> : null}
              {stat.label}
            </span>
            <span className="admin-stat__value">{stat.value}</span>
            {stat.hint ? <span className="admin-stat__hint">{stat.hint}</span> : null}
          </>
        );
        return (
          <li key={stat.key} className="admin-stat" data-tone={stat.tone ?? "neutral"}>
            {stat.to ? (
              <Link to={stat.to} className="admin-stat__link">
                {body}
              </Link>
            ) : (
              body
            )}
          </li>
        );
      })}
    </ul>
  );
}

export function StatusBadge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span className="status-badge" data-tone={tone}>
      <span className="status-badge__dot" aria-hidden="true" />
      {children}
    </span>
  );
}

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  align?: "start" | "end" | undefined;
  /** Shown as the card title on phones. */
  primary?: boolean | undefined;
  width?: string | undefined;
}

export function AdminTable<T>({
  columns,
  rows,
  rowKey,
  label,
  empty,
  actions,
}: {
  columns: Column<T>[];
  rows: readonly T[];
  rowKey: (row: T) => string;
  label: string;
  empty?: ReactNode | undefined;
  /** Buttons at the end of each row. */
  actions?: (row: T) => ReactNode | undefined;
}) {
  if (rows.length === 0) return <>{empty ?? null}</>;
  return (
    <div className="admin-table-wrap">
      <table className="admin-table" aria-label={label}>
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                data-align={column.align}
                style={column.width ? { inlineSize: column.width } : undefined}
              >
                {column.header}
              </th>
            ))}
            {actions ? (
              <th scope="col" data-align="end">
                <span className="visually-hidden">{label}</span>
              </th>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((column) => (
                <td
                  key={column.key}
                  data-label={column.header}
                  data-align={column.align}
                  data-primary={column.primary || undefined}
                >
                  {column.render(row)}
                </td>
              ))}
              {actions ? (
                <td data-align="end" className="admin-table__actions">
                  {actions(row)}
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AdminToolbar({ children }: { children: ReactNode }) {
  return <div className="admin-toolbar">{children}</div>;
}

export function SearchBox({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="admin-search">
      <Icon name="search" size={18} />
      <span className="visually-hidden">{label}</span>
      <input
        type="search"
        value={value}
        placeholder={label}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

export function FormGrid({ children }: { children: ReactNode }) {
  return <div className="admin-form-grid">{children}</div>;
}

/** A form's actions — in a dialog, they go to its footer, on the same line as « Cancel » (027). */
export function FormActions({ children }: { children: ReactNode }) {
  const inDialog = useInDialog();
  return inDialog ? (
    <DialogActions>{children}</DialogActions>
  ) : (
    <div className="admin-form-actions">{children}</div>
  );
}

export function KeyValues({ items }: { items: Array<{ key: string; label: string; value: ReactNode }> }) {
  return (
    <dl className="admin-kv">
      {items.map((item) => (
        <div key={item.key}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function AdminEmpty({
  icon = "inbox",
  title,
  message,
  action,
}: {
  icon?: string | undefined;
  title: string;
  message?: ReactNode | undefined;
  action?: ReactNode | undefined;
}) {
  return (
    <div className="admin-empty">
      <EmptyState icon={icon} title={title} message={message} action={action ?? null} />
    </div>
  );
}

/** A labelled JSON document editor (definitions, schemas): monospace, wide, with its own error line. */
export function JsonField({
  id: givenId,
  label,
  value,
  onChange,
  error,
  rows = 12,
}: {
  id?: string | undefined;
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string | null | undefined;
  rows?: number | undefined;
}) {
  const generated = useId();
  const id = givenId ?? generated;
  return (
    <div className="ds-field admin-json">
      <label htmlFor={id}>{label}</label>
      <textarea
        id={id}
        rows={rows}
        spellCheck={false}
        value={value}
        aria-invalid={error ? true : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
      {error ? (
        <span className="ds-field__error" role="alert">
          {error}
        </span>
      ) : null}
    </div>
  );
}

/**
 * A task that is running (027): a spinner, what it is doing (« 1 234 / 6 000 »), and a bar — determinate
 * when the total is known, indeterminate otherwise. The spinner stops for reduced motion.
 */
export function LiveProgress({
  label,
  done,
  total,
  detail,
}: {
  label: string;
  done?: number | null | undefined;
  total?: number | null | undefined;
  detail?: ReactNode | undefined;
}) {
  const known = typeof total === "number" && total > 0 && typeof done === "number";
  return (
    <span className="live-progress" role="status">
      <span className="live-progress__line">
        <Icon name="spinner" size={16} className="live-progress__spinner" />
        <span>{label}</span>
        {detail ? <span className="live-progress__detail">{detail}</span> : null}
      </span>
      <Progress label={label} value={known ? (done ?? 0) : null} max={known ? (total ?? 1) : 100} />
    </span>
  );
}
