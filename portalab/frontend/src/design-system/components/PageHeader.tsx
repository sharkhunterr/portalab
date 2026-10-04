import type { ReactNode } from "react";
import { Button } from "./Button";
import { Icon } from "./Icon";

/**
 * ``PageHeader`` (spec 027 FR-023, R20): every routed page opens with it — title, an optional context
 * line, one primary action and secondary actions, optionally over artwork. Where am I / what can I do is
 * answered in the same place on every page (constitution X).
 */
export interface PageAction {
  label: string;
  icon?: string;
  onSelect?: () => void;
  href?: string;
  disabled?: boolean;
}

export interface PageHeaderProps {
  title: string;
  context?: ReactNode;
  icon?: string;
  primary?: PageAction | ReactNode;
  secondary?: ReactNode;
  /** Image URL shown behind the header (media detail pages). */
  artwork?: string | null;
  children?: ReactNode;
}

function isAction(value: unknown): value is PageAction {
  return typeof value === "object" && value !== null && "label" in value && !("$$typeof" in value);
}

function ActionButton({ action }: { action: PageAction }) {
  const content = (
    <>
      {action.icon ? <Icon name={action.icon} size={18} /> : null}
      {action.label}
    </>
  );
  if (action.href) {
    return (
      <a className="ds-button ds-button--primary" href={action.href}>
        {content}
      </a>
    );
  }
  return (
    <Button variant="primary" onClick={action.onSelect} disabled={action.disabled}>
      {content}
    </Button>
  );
}

export function PageHeader({ title, context, icon, primary, secondary, artwork, children }: PageHeaderProps) {
  return (
    <header className="ds-page-header" data-artwork={artwork ? "true" : undefined}>
      {artwork ? (
        <div className="ds-page-header__art" aria-hidden="true">
          <img src={artwork} alt="" />
        </div>
      ) : null}
      <div className="ds-page-header__body">
        <div className="ds-page-header__text">
          <h1 className="ds-page-header__title">
            {icon ? <Icon name={icon} size={26} className="ds-page-header__icon" /> : null}
            {title}
          </h1>
          {context ? <p className="ds-page-header__context">{context}</p> : null}
        </div>
        {primary || secondary ? (
          <div className="ds-page-header__actions">
            {secondary}
            {isAction(primary) ? <ActionButton action={primary} /> : primary}
          </div>
        ) : null}
      </div>
      {children}
    </header>
  );
}
