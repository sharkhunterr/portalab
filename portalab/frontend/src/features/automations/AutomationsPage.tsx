import { useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router";
import {
  AdminEmpty,
  AdminPage,
  AdminSection,
  AdminStats,
  StatusBadge,
  type Tone,
} from "../../design-system/admin/AdminKit";
import { Button } from "../../design-system/components/Button";
import { TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { ApiError } from "../../state/regions";
import { useServiceNames } from "../support/incidents/maintenance";
import {
  type AutomationSummary,
  type Definition,
  type DryRun,
  useApprovals,
  useAutomation,
  useAutomationAdmin,
  useAutomations,
  useCatalog,
  useRecentExecutions,
  useTemplates,
} from "./api";
import { Inbox } from "./approvals/Inbox";
import { Editor } from "./editor/Editor";
import { FlowView } from "./flow/FlowView";
import { ExecutionList, STATUS_TONES } from "./history/ExecutionList";
import {
  actionLabel,
  conditionLabel,
  paramLabel,
  serviceNames,
  TRIGGER_ICONS,
  triggerSummary,
} from "./labels";
import { Gallery } from "./templates/Gallery";
import "./automations.css";

/**
 * Automations (spec 019; 027: a hub of its own) — overview, new automation, an automation and its runs,
 * editing it, the run history of all of them, templates and approvals.
 */
export default function AutomationsPage() {
  const { id } = useParams();
  const { pathname } = useLocation();
  if (id && pathname.endsWith("/edit")) return <EditPage id={id} />;
  if (id) return <DetailPage id={id} />;
  if (pathname.endsWith("/new")) return <NewPage />;
  if (pathname.endsWith("/history")) return <HistoryPage />;
  if (pathname.endsWith("/templates")) return <TemplatesPage />;
  if (pathname.endsWith("/approvals")) return <ApprovalsPage />;
  return <Overview />;
}

const STATE_TONES: Record<string, Tone> = {
  active: "ok",
  draft: "neutral",
  paused: "warn",
  suspended: "bad",
  archived: "neutral",
};

function NewButton() {
  const t = useT();
  return (
    <Link className="ds-button ds-button--primary" to="/admin/automations/new">
      <Icon name="plus" size={18} />
      {t("automations:new")}
    </Link>
  );
}

function Overview() {
  const t = useT();
  const format = useFormat();
  const automations = useAutomations();
  const approvals = useApprovals();
  const catalog = useCatalog().data;
  const names = useServiceNames().data;
  if (names) serviceNames.current = names; // service ids read as names in the triggers
  const [filter, setFilter] = useState<"all" | "active" | "attention" | "draft">("all");
  const items = automations.data ?? [];
  const attention = (a: AutomationSummary) => a.state === "suspended" || a.needs_review || a.failures_7d > 0;
  const shown = items.filter((a) =>
    filter === "all"
      ? a.state !== "archived"
      : filter === "active"
        ? a.state === "active"
        : filter === "draft"
          ? a.state === "draft"
          : attention(a),
  );
  const runs = items.reduce((sum, a) => sum + a.runs_7d, 0);
  const failures = items.reduce((sum, a) => sum + a.failures_7d, 0);
  return (
    <AdminPage
      icon="zap"
      title={t("automations:title")}
      description={t("automations:description")}
      primary={<NewButton />}
      secondary={
        <Link className="ds-button ds-button--ghost" to="/admin/automations/templates">
          <Icon name="sparkles" size={16} />
          {t("automations:templates.title")}
        </Link>
      }
    >
      <AdminStats
        label={t("automations:title")}
        stats={[
          {
            key: "active",
            label: t("automations:stats.active"),
            value: items.filter((a) => a.state === "active").length,
            icon: "zap",
            tone: "ok",
          },
          {
            key: "runs",
            label: t("automations:stats.runs"),
            value: runs,
            icon: "activity",
            to: "/admin/automations/history",
          },
          {
            key: "failures",
            label: t("automations:stats.failures"),
            value: failures,
            icon: "alert",
            tone: failures ? "bad" : "neutral",
            to: "/admin/automations/history",
          },
          {
            key: "approvals",
            label: t("automations:approvals.title"),
            value: approvals.data?.length ?? 0,
            icon: "check",
            tone: approvals.data?.length ? "warn" : "neutral",
            to: "/admin/automations/approvals",
          },
        ]}
      />
      <div className="automation-filters" role="tablist" aria-label={t("automations:filter.label")}>
        {(["all", "active", "attention", "draft"] as const).map((key) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={filter === key}
            className="automation-filter"
            onClick={() => setFilter(key)}
          >
            {t(`automations:filter.${key}`)}
          </button>
        ))}
      </div>
      {automations.isPending ? <FunctionalState state="loading" /> : null}
      {!automations.isPending && shown.length === 0 ? (
        <AdminEmpty
          icon="zap"
          title={t("automations:none")}
          action={
            <Link className="ds-button ds-button--secondary" to="/admin/automations/templates">
              {t("automations:templates.title")}
            </Link>
          }
        />
      ) : null}
      <ul className="automation-cards">
        {shown.map((a) => (
          <li key={a.id}>
            <Link to={`/admin/automations/${a.id}`} className="automation-card" data-state={a.state}>
              <span className="automation-card__icon" aria-hidden="true">
                <Icon name={TRIGGER_ICONS[String(a.trigger?.kind ?? "event")] ?? "zap"} size={20} />
              </span>
              <span className="automation-card__main">
                <span className="automation-card__title">
                  <strong>{a.name}</strong>
                  <StatusBadge tone={STATE_TONES[a.state] ?? "neutral"}>
                    {t(`automations:state.${a.state}`)}
                  </StatusBadge>
                  {a.needs_review ? (
                    <StatusBadge tone="warn">{t("automations:needsReview")}</StatusBadge>
                  ) : null}
                  {a.published_version !== null && a.current_version !== a.published_version ? (
                    <StatusBadge tone="info">{t("automations:unpublished")}</StatusBadge>
                  ) : null}
                </span>
                <span className="automation-card__when">
                  {triggerSummary(t, a.trigger as Definition["trigger"] | null, catalog, format)}
                </span>
                <span className="automation-card__steps">
                  {(a.steps ?? []).map((action, index) => (
                    // biome-ignore lint/suspicious/noArrayIndexKey: steps are positional
                    <span key={index} className="automation-chip automation-chip--quiet">
                      {actionLabel(t, action, catalog)}
                    </span>
                  ))}
                </span>
              </span>
              <span className="automation-card__last">
                {a.last_status ? (
                  <>
                    <StatusBadge tone={STATUS_TONES[a.last_status] ?? "neutral"}>
                      {t(`automations:status.${a.last_status}`)}
                    </StatusBadge>
                    <span className="automation-meta">
                      {a.last_run_at ? format.relative((Date.parse(a.last_run_at) - Date.now()) / 1000) : ""}
                    </span>
                  </>
                ) : (
                  <span className="automation-meta">{t("automations:neverRun")}</span>
                )}
                <span className="automation-meta">{t("automations:runs7d", { count: a.runs_7d })}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </AdminPage>
  );
}

function NewPage() {
  const t = useT();
  const [params] = useSearchParams();
  const templates = useTemplates();
  const chosen = params.get("template");
  const template = chosen ? templates.data?.find((tpl) => tpl.key === chosen) : undefined;
  if (chosen && templates.isPending) return <FunctionalState state="loading" />;
  return (
    <AdminPage
      icon="plus"
      title={template ? template.title : t("automations:new")}
      description={template ? template.description : t("automations:editor.intro")}
    >
      <Editor
        key={template?.key ?? "blank"}
        initial={template?.definition}
        initialKey={template ? template.key.replaceAll("-", "_") : undefined}
      />
    </AdminPage>
  );
}

function EditPage({ id }: { id: string }) {
  const t = useT();
  const automation = useAutomation(id);
  if (!automation.data) return <FunctionalState state={automation.isError ? "unavailable" : "loading"} />;
  return (
    <AdminPage icon="settings" title={t("automations:editor.editTitle", { name: automation.data.name })}>
      <Editor
        automationId={id}
        initial={automation.data.definition as unknown as Definition}
        initialKey={automation.data.key}
      />
    </AdminPage>
  );
}

function DetailPage({ id }: { id: string }) {
  const t = useT();
  const navigate = useNavigate();
  const automation = useAutomation(id);
  const admin = useAutomationAdmin();
  const list = useAutomations();
  const [token, setToken] = useState<string | null>(null);
  if (!automation.data) return <FunctionalState state={automation.isError ? "unavailable" : "loading"} />;
  const a = automation.data;
  const summary = list.data?.find((item) => item.id === id);
  const definition = a.definition as unknown as Definition;
  const unpublished = a.published_version === null || a.current_version !== a.published_version;
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
  const transitions: Array<"pause" | "resume" | "reenable" | "archive"> =
    a.state === "active"
      ? ["pause"]
      : a.state === "paused"
        ? ["resume"]
        : a.state === "suspended"
          ? ["reenable"]
          : [];
  return (
    <AdminPage
      icon="zap"
      title={a.name}
      description={
        <span className="automation-detail__meta">
          <StatusBadge tone={STATE_TONES[a.state] ?? "neutral"}>
            {t(`automations:state.${a.state}`)}
          </StatusBadge>
          <span>
            {t("automations:versionOf", {
              current: a.current_version,
              published: a.published_version ?? "—",
            })}
          </span>
          <code>{a.key}</code>
        </span>
      }
      primary={
        unpublished && a.state !== "archived" ? (
          <Button onClick={() => publish()} disabled={admin.publish.isPending}>
            <Icon name="zap" size={16} />
            {t("automations:publish")}
          </Button>
        ) : undefined
      }
      secondary={
        <>
          <Link className="ds-button ds-button--secondary" to={`/admin/automations/${id}/edit`}>
            <Icon name="settings" size={16} />
            {t("automations:edit")}
          </Link>
          {transitions.map((transition) => (
            <Button
              key={transition}
              variant="ghost"
              onClick={() => admin.transition.mutate({ id, transition })}
            >
              {t(`automations:action.${transition}`)}
            </Button>
          ))}
          {a.state !== "archived" ? (
            <Button
              variant="ghost"
              onClick={() =>
                admin.transition.mutate(
                  { id, transition: "archive" },
                  { onSuccess: () => navigate("/admin/automations") },
                )
              }
            >
              <Icon name="trash" size={16} />
              {t("automations:action.archive")}
            </Button>
          ) : null}
        </>
      }
    >
      {a.state === "suspended" ? (
        <p role="alert" className="automation-banner" data-tone="bad">
          <Icon name="alert" size={16} />{" "}
          {t("automations:suspended.banner", { reason: a.suspend_reason ?? "" })}
        </p>
      ) : null}
      {token ? (
        <div
          role="alertdialog"
          aria-labelledby="automation-confirm"
          className="automation-banner"
          data-tone="warn"
        >
          <p id="automation-confirm">
            <Icon name="shield" size={16} /> {t("automations:confirm")}
          </p>
          <Button onClick={() => publish(token)}>{t("automations:confirmPublish")}</Button>
          <Button variant="ghost" onClick={() => setToken(null)}>
            {t("automations:editor.cancel")}
          </Button>
        </div>
      ) : null}
      {unpublished && a.state !== "archived" && !token ? (
        <p className="automation-banner" data-tone="info">
          <Icon name="info" size={16} /> {t("automations:draftHint")}
        </p>
      ) : null}
      {summary ? (
        <AdminStats
          label={t("automations:history.title")}
          stats={[
            { key: "runs", label: t("automations:stats.runs"), value: summary.runs_7d, icon: "activity" },
            {
              key: "failures",
              label: t("automations:stats.failures"),
              value: summary.failures_7d,
              icon: "alert",
              tone: summary.failures_7d ? "bad" : "neutral",
            },
            {
              key: "last",
              label: t("automations:stats.last"),
              value: summary.last_status ? t(`automations:status.${summary.last_status}`) : "—",
              icon: "clock",
              tone: summary.last_status ? (STATUS_TONES[summary.last_status] ?? "neutral") : "neutral",
            },
          ]}
        />
      ) : null}
      <div className="automation-detail">
        <AdminSection title={t("automations:flow.title")} icon="activity">
          <FlowView definition={definition} />
        </AdminSection>
        <AdminSection
          title={t("automations:test.title")}
          icon="play"
          description={t("automations:test.hint")}
        >
          <TestPanel id={id} definition={definition} />
        </AdminSection>
      </div>
      <AdminSection title={t("automations:history.title")} icon="clock" flush>
        <ExecutionList automationId={id} />
      </AdminSection>
    </AdminPage>
  );
}

/** A dry run with a sample event: the event's fields as inputs, the verdict of each condition and step. */
function TestPanel({ id, definition }: { id: string; definition: Definition }) {
  const t = useT();
  const catalog = useCatalog().data;
  const admin = useAutomationAdmin();
  const eventType = definition.trigger.event_type ?? "";
  const fields = catalog?.triggers.event_fields?.[eventType] ?? [];
  const [sample, setSample] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      (definition.trigger.filter ?? []).map((f) => [
        f.field,
        Array.isArray(f.value) ? String(f.value[0]) : String(f.value),
      ]),
    ),
  );
  const [plan, setPlan] = useState<DryRun | null>(null);
  const payload = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(sample)
          .filter(([, v]) => v.trim() !== "")
          .map(([k, v]) => [k, v.trim() !== "" && Number.isFinite(Number(v)) ? Number(v) : v]),
      ),
    [sample],
  );
  return (
    <div className="automation-test">
      {fields.length ? (
        <div className="automation-params">
          {fields.map((field) => (
            <TextField
              key={field}
              label={paramLabel(t, field)}
              value={sample[field] ?? ""}
              onChange={(e) => setSample({ ...sample, [field]: e.target.value })}
            />
          ))}
        </div>
      ) : (
        <p className="automation-meta">{t("automations:test.noFields")}</p>
      )}
      <Button
        variant="secondary"
        disabled={admin.dryRun.isPending}
        onClick={() => admin.dryRun.mutate({ id, payload }, { onSuccess: setPlan })}
      >
        <Icon name={admin.dryRun.isPending ? "spinner" : "play"} size={16} />
        {t("automations:action.dryRun")}
      </Button>
      {plan ? (
        <section aria-live="polite" className="automation-plan" data-ok={plan.conditions_passed || undefined}>
          <p>
            <Icon name={plan.conditions_passed ? "check" : "close"} size={16} />{" "}
            {plan.conditions_passed ? t("automations:dryRun.ok") : t("automations:dryRun.failed")}
          </p>
          {plan.trace.length ? (
            <ul className="automation-trace">
              {plan.trace.map((item, index) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: the trace is positional
                <li key={index} data-result={String(item.result)}>
                  <Icon
                    name={item.result === true ? "check" : item.result === false ? "close" : "info"}
                    size={12}
                  />
                  {conditionLabel(t, item.leaf, catalog)} —{" "}
                  {t(`automations:history.result.${String(item.result)}`)}
                </li>
              ))}
            </ul>
          ) : null}
          <ol className="automation-plan__steps">
            {plan.planned_if_passed.map((step) => (
              <li key={step.id}>
                <strong>{actionLabel(t, step.action, catalog)}</strong>
                {step.approval ? (
                  <StatusBadge tone="info">{t("automations:dryRun.approval")}</StatusBadge>
                ) : null}
                {step.allowed === false ? (
                  <StatusBadge tone="bad">{t("automations:dryRun.forbidden")}</StatusBadge>
                ) : null}
                {step.params && typeof step.params === "object" ? (
                  <dl className="automation-flow__params">
                    {Object.entries(step.params as Record<string, unknown>).map(([name, value]) => (
                      <div key={name}>
                        <dt>{paramLabel(t, name)}</dt>
                        <dd>{typeof value === "object" ? JSON.stringify(value) : String(value)}</dd>
                      </div>
                    ))}
                  </dl>
                ) : null}
              </li>
            ))}
          </ol>
        </section>
      ) : null}
    </div>
  );
}

function HistoryPage() {
  const t = useT();
  const [status, setStatus] = useState("");
  const executions = useRecentExecutions(status || undefined);
  const automations = useAutomations();
  const names = new Map((automations.data ?? []).map((a) => [a.id, a.name]));
  return (
    <AdminPage
      icon="clock"
      title={t("automations:history.allTitle")}
      description={t("automations:history.allHint")}
    >
      <div className="automation-filters" role="tablist" aria-label={t("automations:filter.label")}>
        {["", "success", "failed", "no_op", "awaiting_approval"].map((key) => (
          <button
            key={key || "all"}
            type="button"
            role="tab"
            aria-selected={status === key}
            className="automation-filter"
            onClick={() => setStatus(key)}
          >
            {key ? t(`automations:status.${key}`) : t("automations:filter.all")}
          </button>
        ))}
      </div>
      {executions.isPending ? <FunctionalState state="loading" /> : null}
      <AdminSection title={t("automations:history.title")} icon="clock" flush>
        <ExecutionList executions={executions.data ?? []} names={names} />
      </AdminSection>
    </AdminPage>
  );
}

function TemplatesPage() {
  const t = useT();
  return (
    <AdminPage
      icon="sparkles"
      title={t("automations:templates.title")}
      description={t("automations:templates.hint")}
    >
      <Gallery />
    </AdminPage>
  );
}

function ApprovalsPage() {
  const t = useT();
  return (
    <AdminPage
      icon="check"
      title={t("automations:approvals.title")}
      description={t("automations:approvals.hint")}
    >
      <Inbox />
    </AdminPage>
  );
}
