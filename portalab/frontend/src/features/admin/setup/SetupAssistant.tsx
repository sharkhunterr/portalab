import { type ReactNode, useId } from "react";
import { Link, useNavigate } from "react-router";
import { AdminPage, StatusBadge } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { SettingCard, type SettingItem } from "../ConfigEditor";
import { EmailSettings } from "../communication/EmailSettings";
import { AddServiceWizard } from "../services/ServicesAdmin";
import { SiteIdentityAdmin } from "../site/SiteIdentityAdmin";
import { type Progress, STEPS, type Step, type StepKey, useReadiness, useSetupProgress } from "./progress";
import "./setup.css";

/**
 * Issue 6 — the setup assistant: the portal set up step by step after its first run — its identity, the
 * administrator's account, who may join, the services, the media, communication, the look, play and shop, the
 * assistant — then what is left to do. Each step holds the real settings and screens (nothing is set twice),
 * may be skipped and come back to; where it is (``admin.setup.progress``) is kept by the server, so it resumes
 * on any device and is opened again from the Control Center without losing anything. Every change goes
 * through the configuration (validated, audited); secrets are never shown back.
 */
function StepSettings({ keys, settings }: { keys: readonly string[]; settings: SettingItem[] }) {
  const items = keys
    .map((key) => settings.find((s) => s.key === key))
    .filter((item): item is SettingItem => Boolean(item));
  if (!items.length) return null;
  return (
    <ul className="setting-cards setup-step__settings">
      {items.map((item) => (
        <SettingCard key={`${item.key}:${JSON.stringify(item.value)}`} item={item} />
      ))}
    </ul>
  );
}

function StepBody({ step, settings }: { step: Step; settings: SettingItem[] }) {
  const embedded: Partial<Record<StepKey, ReactNode>> = {
    identity: <SiteIdentityAdmin embedded />,
    services: <AddServiceWizard />,
    communication: <EmailSettings />,
  };
  return (
    <>
      {embedded[step.key] ?? null}
      {step.settings ? <StepSettings keys={step.settings} settings={settings} /> : null}
    </>
  );
}

function Links({ step }: { step: Step }) {
  const t = useT();
  if (!step.links?.length) return null;
  return (
    <p className="setup-step__links">
      {step.links.map(([to, label]) => (
        <Link key={to} to={to} className="ds-button ds-button--ghost">
          <Icon name="link" size={14} />
          {t(`admin:setup.link.${label}`)}
        </Link>
      ))}
    </p>
  );
}

function Summary({
  progress,
  ready,
  go,
}: {
  progress: Progress;
  ready: Partial<Record<StepKey, boolean>>;
  go: (step: StepKey) => void;
}) {
  const t = useT();
  return (
    <ul className="setup-summary">
      {STEPS.filter((s) => s.key !== "summary").map((step) => {
        const state =
          ready[step.key] === true || progress.done?.includes(step.key)
            ? "done"
            : progress.skipped?.includes(step.key)
              ? "skipped"
              : "todo";
        return (
          <li key={step.key} data-state={state}>
            <Icon name={step.icon} size={18} />
            <span className="setup-summary__text">
              <strong>{t(`admin:setup.step.${step.key}.title`)}</strong>
              <span>{t(`admin:setup.step.${step.key}.todo`)}</span>
            </span>
            <StatusBadge tone={state === "done" ? "ok" : state === "skipped" ? "neutral" : "warn"}>
              {t(`admin:setup.state.${state}`)}
            </StatusBadge>
            <Button variant="ghost" onClick={() => go(step.key)}>
              {t("admin:setup.open")}
            </Button>
          </li>
        );
      })}
    </ul>
  );
}

export function SetupAssistant() {
  const t = useT();
  const navigate = useNavigate();
  const titleId = useId();
  const { settings, progress, save } = useSetupProgress();
  const ready = useReadiness(settings.data);
  const current = STEPS.find((s) => s.key === progress.step) ?? (STEPS[0] as Step);
  const index = STEPS.indexOf(current);
  const move = (to: StepKey, mark?: "done" | "skipped") => {
    const without = (list: StepKey[] | undefined) => (list ?? []).filter((k) => k !== current.key);
    save.mutate({
      ...progress,
      step: to,
      done: mark === "done" ? [...without(progress.done), current.key] : (progress.done ?? []),
      skipped: mark === "skipped" ? [...without(progress.skipped), current.key] : (progress.skipped ?? []),
    });
  };
  const next = STEPS[index + 1]?.key;
  const previous = STEPS[index - 1]?.key;
  const finish = () =>
    save.mutate(
      { ...progress, step: "summary", finished_at: new Date().toISOString() },
      { onSuccess: () => navigate("/admin") },
    );
  return (
    <AdminPage icon="rocket" title={t("admin:setup.title")} description={t("admin:setup.subtitle")} wide>
      <div className="setup">
        <nav className="setup__steps" aria-label={t("admin:setup.steps")}>
          <ol>
            {STEPS.map((step, position) => {
              const done = ready[step.key] === true || progress.done?.includes(step.key);
              return (
                <li key={step.key}>
                  <button
                    type="button"
                    aria-current={step.key === current.key ? "step" : undefined}
                    data-done={done || undefined}
                    data-skipped={progress.skipped?.includes(step.key) || undefined}
                    onClick={() => save.mutate({ ...progress, step: step.key })}
                  >
                    <span className="setup__number" aria-hidden="true">
                      {done ? <Icon name="check" size={14} /> : position + 1}
                    </span>
                    <span>{t(`admin:setup.step.${step.key}.title`)}</span>
                  </button>
                </li>
              );
            })}
          </ol>
        </nav>
        <section className="setup-step" aria-labelledby={titleId}>
          <header className="setup-step__head">
            <span className="setup-step__icon" aria-hidden="true">
              <Icon name={current.icon} size={24} />
            </span>
            <div>
              <p className="setup-step__count">
                {t("admin:setup.count", { step: index + 1, total: STEPS.length })}
              </p>
              <h2 id={titleId}>{t(`admin:setup.step.${current.key}.title`)}</h2>
              <p>{t(`admin:setup.step.${current.key}.lead`)}</p>
            </div>
          </header>
          {current.key === "summary" ? (
            <Summary progress={progress} ready={ready} go={(step) => save.mutate({ ...progress, step })} />
          ) : settings.data ? (
            <StepBody step={current} settings={settings.data} />
          ) : null}
          <Links step={current} />
          <footer className="setup-step__actions">
            {previous ? (
              <Button variant="ghost" onClick={() => move(previous)} disabled={save.isPending}>
                <Icon name="back" size={16} />
                {t("admin:setup.previous")}
              </Button>
            ) : (
              <span />
            )}
            {next ? (
              <span className="setup-step__forward">
                <Button variant="ghost" onClick={() => move(next, "skipped")} disabled={save.isPending}>
                  {t("admin:setup.skip")}
                </Button>
                <Button onClick={() => move(next, "done")} disabled={save.isPending}>
                  {t("admin:setup.next")}
                  <Icon name="chevron-right" size={16} />
                </Button>
              </span>
            ) : (
              <Button onClick={finish} disabled={save.isPending}>
                <Icon name="check" size={16} />
                {t("admin:setup.finish")}
              </Button>
            )}
          </footer>
        </section>
      </div>
    </AdminPage>
  );
}

export default SetupAssistant;
