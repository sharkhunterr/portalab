import { type InputHTMLAttributes, type ReactNode, useId } from "react";
import { Icon } from "../../design-system/components/Icon";
import { PageHeader } from "../../design-system/components/PageHeader";
import "./account.css";

/**
 * The « My account » kit (#46): every tab of the profile hub drawn alike — a page header, then cards in the
 * look of the Appearance tab (an icon, a title, one line saying what it is for, the settings). Theme tokens
 * only, so every theme dresses them.
 */
export function SettingsPage({
  icon,
  title,
  lead,
  actions,
  children,
  className,
}: {
  icon: string;
  title: string;
  lead?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const headingId = useId();
  return (
    <section aria-labelledby={headingId} className={["settings-page", className].filter(Boolean).join(" ")}>
      <PageHeader
        titleId={headingId}
        level={2}
        icon={icon}
        title={title}
        context={lead}
        secondary={actions}
      />
      {children}
    </section>
  );
}

export function SettingsCard({
  icon,
  title,
  hint,
  aside,
  children,
  tone,
  id,
  level = 3,
  ...rest
}: {
  icon: string;
  title: string;
  hint?: ReactNode;
  /** Shown at the end of the card's header (a status, a link). */
  aside?: ReactNode;
  children?: ReactNode;
  /** ``danger``: an irreversible action lives here. */
  tone?: "danger";
  id?: string;
  /** The title's heading level (2 when the page has no section titles above it). */
  level?: 2 | 3;
  "data-section"?: string;
}) {
  const headingId = useId();
  const Heading = level === 2 ? "h2" : "h3";
  return (
    <section className="settings-card" aria-labelledby={headingId} data-tone={tone} id={id} {...rest}>
      <header className="settings-card__head">
        <span className="settings-card__icon" aria-hidden="true">
          <Icon name={icon} size={20} />
        </span>
        <div className="settings-card__title">
          <Heading id={headingId}>{title}</Heading>
          {hint ? <p>{hint}</p> : null}
        </div>
        {aside ? <div className="settings-card__aside">{aside}</div> : null}
      </header>
      {children ? <div className="settings-card__body">{children}</div> : null}
    </section>
  );
}

/** A grid of settings cards (two columns where there is room). */
export function SettingsGrid({ children }: { children: ReactNode }) {
  return <div className="settings-grid">{children}</div>;
}

/**
 * A switch: a real checkbox (keyboard, screen readers, forms) drawn as a toggle; its label may be visually
 * hidden when a table header already says it.
 */
export function Switch({
  label,
  hideLabel = false,
  ...props
}: Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & { label: string; hideLabel?: boolean }) {
  return (
    <label className="settings-switch" data-disabled={props.disabled || undefined}>
      <input type="checkbox" {...props} {...(hideLabel ? { "aria-label": label } : {})} />
      <span className="settings-switch__track" aria-hidden="true">
        <span className="settings-switch__thumb" />
      </span>
      {hideLabel ? null : <span className="settings-switch__label">{label}</span>}
    </label>
  );
}

/** « Saved » said politely, next to what was changed. */
export function SavedNote({ shown, text }: { shown: boolean; text: string }) {
  return (
    <span className="settings-saved" role="status" data-shown={shown || undefined}>
      {shown ? (
        <>
          <Icon name="check" size={14} />
          {text}
        </>
      ) : null}
    </span>
  );
}
