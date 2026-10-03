import { useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { type Execution, useExecutions } from "../api";

/** Execution history (spec 019 T027): status **in text**, condition trace and per-step outcomes. */
export function ExecutionList({ automationId }: { automationId: string }) {
  const t = useT();
  const format = useFormat();
  const executions = useExecutions(automationId);
  const [open, setOpen] = useState<string | null>(null);
  if (executions.data?.length === 0) return <p>{t("automations:history.empty")}</p>;
  return (
    <section aria-label={t("automations:history.title")}>
      <h3>{t("automations:history.title")}</h3>
      <ul className="ds-stack">
        {(executions.data ?? []).map((execution) => (
          <li key={execution.id} data-status={execution.status}>
            <Button
              variant="secondary"
              aria-expanded={open === execution.id}
              onClick={() => setOpen(open === execution.id ? null : execution.id)}
            >
              {format.dateTime(execution.started_at)} · {t(`automations:status.${execution.status}`)}
              {execution.error_code ? ` (${execution.error_code})` : ""}
              {execution.batch_count > 1
                ? ` · ${t("automations:history.batched", { count: execution.batch_count })}`
                : ""}
            </Button>
            {open === execution.id ? <ExecutionDetail execution={execution} /> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function ExecutionDetail({ execution }: { execution: Execution }) {
  const t = useT();
  return (
    <div className="ds-card ds-stack">
      <h4>{t("automations:history.trace")}</h4>
      <ul>
        {execution.conditions_trace.map((item, index) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: the trace is positional
          <li key={index}>
            {String(item.leaf)} — {String(item.result)}
          </li>
        ))}
      </ul>
      <h4>{t("automations:history.steps")}</h4>
      <ol>
        {execution.steps.map((step) => (
          <li key={String(step.id)}>
            {String(step.action)} — {String(step.status)}
            {step.error_code ? ` (${String(step.error_code)})` : ""}
          </li>
        ))}
      </ol>
    </div>
  );
}
