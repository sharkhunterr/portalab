import { useState } from "react";
import { Link } from "react-router";
import { StatusBadge, type Tone } from "../../../design-system/admin/AdminKit";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { type Catalog, type Execution, useCatalog, useExecutions } from "../api";
import { ACTION_ICONS, actionLabel, conditionLabel, eventLabel, maybe } from "../labels";

/**
 * Run history (spec 019 T027; 027 redesign): one row per run — when, how it went (a word and a colour,
 * never colour alone), how long, what started it — and, opened, the run as a timeline: the trigger, each
 * condition with its verdict, then each step with its outcome, duration and, when it failed, why.
 */
export const STATUS_TONES: Record<string, Tone> = {
  success: "ok",
  running: "info",
  awaiting_approval: "info",
  no_op: "neutral",
  throttled: "neutral",
  prevented: "warn",
  refused: "bad",
  failed: "bad",
  timeout: "bad",
  suspended: "warn",
};

const STEP_ICONS: Record<string, string> = {
  ok: "check",
  failed: "close",
  refused: "blocked",
  timeout: "hourglass",
  awaiting_approval: "clock",
  skipped: "minus",
};

export function ExecutionList({
  automationId,
  executions: given,
  names,
}: {
  automationId?: string;
  /** a list loaded elsewhere (the run history of every automation) */
  executions?: Execution[] | undefined;
  names?: Map<string, string>;
}) {
  const t = useT();
  const own = useExecutions(automationId ?? "");
  const executions = given ?? (automationId ? own.data : []) ?? [];
  const [open, setOpen] = useState<string | null>(null);
  if (!executions.length) return <p className="automation-meta">{t("automations:history.empty")}</p>;
  return (
    <ul className="automation-runs" aria-label={t("automations:history.title")}>
      {executions.map((execution) => (
        <li key={execution.id} className="automation-run" data-status={execution.status}>
          <RunRow
            execution={execution}
            name={names?.get(execution.automation_id)}
            open={open === execution.id}
            onToggle={() => setOpen(open === execution.id ? null : execution.id)}
          />
          {open === execution.id ? <ExecutionDetail execution={execution} /> : null}
        </li>
      ))}
    </ul>
  );
}

function duration(execution: Execution): number | null {
  if (!execution.finished_at) return null;
  return Math.max(0, Date.parse(execution.finished_at) - Date.parse(execution.started_at));
}

function ms(value: number | null | undefined, t: ReturnType<typeof useT>): string {
  if (value === null || value === undefined) return "";
  return value < 1000
    ? t("automations:history.ms", { value: Math.round(value) })
    : t("automations:history.seconds", { value: Math.round(value / 100) / 10 });
}

function RunRow({
  execution,
  name,
  open,
  onToggle,
}: {
  execution: Execution;
  name?: string | undefined;
  open: boolean;
  onToggle: () => void;
}) {
  const t = useT();
  const format = useFormat();
  const statusText = t(`automations:status.${execution.status}`);
  return (
    <button type="button" className="automation-run__row" aria-expanded={open} onClick={onToggle}>
      <StatusBadge tone={STATUS_TONES[execution.status] ?? "neutral"}>{statusText}</StatusBadge>
      <span className="automation-run__main">
        {name ? <strong>{name}</strong> : null}
        <span className="automation-meta">
          {format.dateTime(execution.started_at)}
          {duration(execution) !== null ? ` · ${ms(duration(execution), t)}` : ""}
          {` · ${t("automations:history.version", { version: execution.version })}`}
          {execution.batch_count > 1
            ? ` · ${t("automations:history.batched", { count: execution.batch_count })}`
            : ""}
        </span>
      </span>
      <span className="automation-run__steps" aria-hidden="true">
        {execution.steps.map((step) => (
          <span key={String(step.id)} data-status={String(step.status)}>
            <Icon name={STEP_ICONS[String(step.status)] ?? "minus"} size={12} />
          </span>
        ))}
      </span>
      <Icon name={open ? "chevron-down" : "chevron-right"} size={16} />
    </button>
  );
}

export function ExecutionDetail({ execution }: { execution: Execution }) {
  const t = useT();
  const format = useFormat();
  const catalog: Catalog | undefined = useCatalog().data;
  const ref = (execution.trigger_ref ?? {}) as Record<string, unknown>;
  const kind = String(ref.type ?? "");
  const startedBy =
    kind === "manual"
      ? t("automations:history.manual")
      : kind === "schedule" || kind === "recurring" || kind === "at" || kind === "relative"
        ? t("automations:history.scheduled", { at: String(ref.fire_at ?? ref.slot ?? "") })
        : eventLabel(t, kind, catalog);
  const trace = execution.conditions_trace;
  return (
    <ol className="automation-timeline">
      <li data-status="ok">
        <span className="automation-timeline__dot" aria-hidden="true">
          <Icon name="zap" size={14} />
        </span>
        <div>
          <strong>{t("automations:history.triggered")}</strong>
          <p className="automation-meta">
            {startedBy}
            {ref.subject ? ` · ${String(ref.subject)}` : ""}
            {ref.occurred_at ? ` · ${format.dateTime(String(ref.occurred_at))}` : ""}
          </p>
        </div>
      </li>
      {trace.length ? (
        <li data-status={execution.status === "no_op" ? "failed" : "ok"}>
          <span className="automation-timeline__dot" aria-hidden="true">
            <Icon name="list" size={14} />
          </span>
          <div>
            <strong>
              {execution.status === "no_op" ? t("automations:history.notMet") : t("automations:history.met")}
            </strong>
            <ul className="automation-trace">
              {trace.map((item, index) => {
                const result = item.result as boolean | "unknown";
                return (
                  // biome-ignore lint/suspicious/noArrayIndexKey: the trace is positional
                  <li key={index} data-result={String(result)}>
                    <Icon name={result === true ? "check" : result === false ? "close" : "info"} size={12} />
                    {conditionLabel(t, String(item.leaf), catalog)} —{" "}
                    {t(`automations:history.result.${String(result)}`)}
                  </li>
                );
              })}
            </ul>
          </div>
        </li>
      ) : null}
      {execution.steps.map((step, index) => {
        const status = String(step.status);
        const error = step.error_code ? String(step.error_code) : null;
        return (
          <li key={String(step.id)} data-status={status}>
            <span className="automation-timeline__dot" aria-hidden="true">
              <Icon name={ACTION_ICONS[String(step.action)] ?? "play"} size={14} />
            </span>
            <div>
              <strong>
                {index + 1}. {actionLabel(t, String(step.action), catalog)}
              </strong>
              <p className="automation-meta">
                {t(`automations:stepStatus.${status}`)}
                {typeof step.duration_ms === "number" ? ` · ${ms(step.duration_ms as number, t)}` : ""}
              </p>
              {error ? (
                <p className="automation-error">
                  <Icon name="alert" size={14} /> {maybe(t, `automations:error.${error}`, error)}
                </p>
              ) : null}
              {step.result && typeof step.result === "object" ? (
                <ResultLinks result={step.result as Record<string, unknown>} />
              ) : null}
            </div>
          </li>
        );
      })}
      {execution.error_code && !execution.steps.some((s) => s.error_code) ? (
        <li data-status="failed">
          <span className="automation-timeline__dot" aria-hidden="true">
            <Icon name="alert" size={14} />
          </span>
          <div>
            <strong>{t("automations:history.stopped")}</strong>
            <p className="automation-error">
              {maybe(t, `automations:error.${execution.error_code}`, execution.error_code)}
            </p>
          </div>
        </li>
      ) : null}
    </ol>
  );
}

/** What a step made (an incident, a ticket…), linked when the portal has a page for it. */
function ResultLinks({ result }: { result: Record<string, unknown> }) {
  const t = useT();
  const entries = Object.entries(result).filter(([, v]) => v !== null && v !== undefined && v !== "");
  if (!entries.length) return null;
  const route = (key: string, value: string) =>
    key === "incident" ? `/incidents/${value}` : key === "ticket" ? `/support/queue/${value}` : null;
  return (
    <ul className="automation-results">
      {entries.map(([key, value]) => {
        const to = route(key, String(value));
        return (
          <li key={key}>
            {to ? (
              <Link to={to}>
                <Icon name="link" size={12} /> {maybe(t, `automations:resultOf.${key}`, key)}
              </Link>
            ) : (
              <span>
                {maybe(t, `automations:resultOf.${key}`, key)} : {String(value)}
              </span>
            )}
          </li>
        );
      })}
    </ul>
  );
}
