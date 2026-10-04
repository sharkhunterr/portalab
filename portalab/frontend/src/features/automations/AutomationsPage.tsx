import { useState } from "react";
import { Link, useParams } from "react-router";
import { Button } from "../../design-system/components/Button";
import { useT } from "../../i18n/hooks/useT";
import { ApiError } from "../../state/regions";
import { type DryRun, useAutomation, useAutomationAdmin, useAutomations } from "./api";
import { Inbox } from "./approvals/Inbox";
import { Builder } from "./builder/Builder";
import { ExecutionList } from "./history/ExecutionList";
import { Gallery } from "./templates/Gallery";
import "./automations.css";
import { PageHeader } from "../../design-system/components/PageHeader";

/** ``/admin/automations`` and ``/admin/automations/:id`` (spec 019). */
export default function AutomationsPage() {
  const { id } = useParams();
  return id ? <AutomationDetail id={id} /> : <Overview />;
}

function Overview() {
  const t = useT();
  const automations = useAutomations();
  return (
    <div className="ds-stack">
      <PageHeader icon="zap" title={t("automations:title")} />
      <ul className="ds-stack">
        {(automations.data ?? []).map((a) => (
          <li key={a.id}>
            <Link to={`/admin/automations/${a.id}`}>{a.name}</Link> · {t(`automations:state.${a.state}`)}
            {a.needs_review ? " ⚠" : ""}
          </li>
        ))}
      </ul>
      <Inbox />
      <Builder />
      <Gallery />
    </div>
  );
}

function AutomationDetail({ id }: { id: string }) {
  const t = useT();
  const automation = useAutomation(id);
  const admin = useAutomationAdmin();
  const [token, setToken] = useState<string | null>(null);
  const [sample, setSample] = useState("{}");
  const [plan, setPlan] = useState<DryRun | null>(null);
  if (!automation.data) return null;
  const a = automation.data;
  const publish = (confirmation?: string) =>
    admin.publish.mutate(
      { id, ...(confirmation ? { confirmation } : {}) },
      {
        onSuccess: () => setToken(null),
        onError: (error) => {
          if (error instanceof ApiError && error.code === "authz.confirmation_required")
            setToken(String(error.extensions.confirmation));
        },
      },
    );
  return (
    <article className="ds-stack">
      <h1>{a.name}</h1>
      {a.state === "suspended" ? (
        <p role="alert" className="automation-banner">
          {t("automations:suspended.banner", { reason: a.suspend_reason ?? "" })}
        </p>
      ) : null}
      <p>
        {t(`automations:state.${a.state}`)} · v{a.current_version}
      </p>
      <div className="ds-stack--row">
        <Button onClick={() => publish()}>{t("automations:publish")}</Button>
        {(["pause", "resume", "reenable", "archive"] as const).map((transition) => (
          <Button
            key={transition}
            variant="secondary"
            onClick={() => admin.transition.mutate({ id, transition })}
          >
            {t(`automations:action.${transition}`)}
          </Button>
        ))}
      </div>
      {token ? (
        <div role="alertdialog" aria-labelledby="automation-confirm" className="ds-card">
          <p id="automation-confirm">{t("automations:confirm")}</p>
          <Button onClick={() => publish(token)}>{t("automations:publish")}</Button>
        </div>
      ) : null}
      <label htmlFor="automation-sample">{t("automations:action.dryRun")}</label>
      <textarea id="automation-sample" rows={3} value={sample} onChange={(e) => setSample(e.target.value)} />
      <Button
        variant="secondary"
        onClick={() => {
          try {
            admin.dryRun.mutate(
              { id, payload: JSON.parse(sample) as Record<string, unknown> },
              { onSuccess: setPlan },
            );
          } catch {
            /* invalid JSON */
          }
        }}
      >
        {t("automations:action.dryRun")}
      </Button>
      {plan ? (
        <section aria-live="polite">
          <p>{plan.conditions_passed ? t("automations:dryRun.ok") : t("automations:dryRun.failed")}</p>
          <ol>
            {plan.planned_if_passed.map((step) => (
              <li key={step.id}>
                {step.action}
                {step.approval ? ` — ${t("automations:dryRun.approval")}` : ""}
                {step.allowed === false ? ` — ${t("automations:dryRun.forbidden")}` : ""}
              </li>
            ))}
          </ol>
        </section>
      ) : null}
      <ExecutionList automationId={id} />
    </article>
  );
}
