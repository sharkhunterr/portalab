import type { ReactNode } from "react";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import "./arrival.css";

/**
 * Issue 249 — the arrival wizard's frame, from the first screen to the portal's opening: a full page of its
 * own (never the portal's shell), the whole way on the side — prepare (before the account exists), set up
 * (signed in: services, members, access, e-mail), open — and the current step as a card that slides in.
 */
export type StageGroup = "prepare" | "configure" | "open";

export interface StageStep {
  key: string;
  group: StageGroup;
  state: "done" | "current" | "todo" | "skipped";
}

export const GROUP_ORDER: readonly StageGroup[] = ["prepare", "configure", "open"];

export function Stage({
  steps,
  children,
  name,
}: {
  steps: readonly StageStep[];
  children: ReactNode;
  name?: string | undefined;
}) {
  const t = useT();
  const position = Math.max(
    0,
    steps.findIndex((s) => s.state === "current"),
  );
  const reached = steps.filter((s) => s.state === "done" || s.state === "skipped").length;
  const share = steps.length ? Math.round((reached / steps.length) * 100) : 0;
  return (
    <div className="arrival-stage">
      <div className="arrival-stage__backdrop" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <aside className="arrival-stage__aside">
        <header className="arrival-stage__brand">
          <span className="arrival-stage__mark" aria-hidden="true">
            <Icon name="sparkles" size={24} />
          </span>
          <div>
            <h1>{name ?? t("account:arrival.title")}</h1>
            <p>{t("account:arrival.subtitle")}</p>
          </div>
        </header>
        {steps.length ? ( // none while the portal is reset
          <div className="arrival-stage__meter">
            <span>{t("account:arrival.count", { step: position + 1, total: steps.length })}</span>
            <span className="arrival-stage__bar" aria-hidden="true">
              <span style={{ inlineSize: `${share}%` }} />
            </span>
          </div>
        ) : null}
        <nav aria-label={t("account:arrival.steps")}>
          {GROUP_ORDER.filter((g) => steps.some((s) => s.group === g)).map((group) => (
            <div key={group} className="arrival-stage__group">
              <p>{t(`account:arrival.group.${group}`)}</p>
              <ol>
                {steps
                  .filter((s) => s.group === group)
                  .map((s) => (
                    <li
                      key={s.key}
                      data-state={s.state}
                      aria-current={s.state === "current" ? "step" : undefined}
                    >
                      <span className="arrival-stage__dot" aria-hidden="true">
                        {s.state === "done" ? <Icon name="check" size={12} /> : null}
                      </span>
                      {t(`account:arrival.step.${s.key}`)}
                    </li>
                  ))}
              </ol>
            </div>
          ))}
        </nav>
      </aside>
      <main className="arrival-stage__main">{children}</main>
    </div>
  );
}

/** One step: its icon, where it is, its title and lead, what it asks, and how to go on. */
export function StepCard({
  id,
  icon,
  title,
  lead,
  children,
  footer,
  stepKey,
}: {
  id: string;
  icon: string;
  title: string;
  lead?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  stepKey: string; // the card slides in again when the step changes
}) {
  return (
    <section key={stepKey} className="arrival-card" aria-labelledby={id}>
      <header className="arrival-card__head">
        <span className="arrival-card__icon" aria-hidden="true">
          <Icon name={icon} size={24} />
        </span>
        <div>
          <h2 id={id}>{title}</h2>
          {lead ? <p className="arrival__lead">{lead}</p> : null}
        </div>
      </header>
      <div className="arrival-card__body">{children}</div>
      {footer ? <footer className="arrival__actions">{footer}</footer> : null}
    </section>
  );
}
