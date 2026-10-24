import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link } from "react-router";
import { api } from "../../../api/client";
import {
  AdminGrid,
  AdminPage,
  AdminSection,
  AdminTable,
  FormActions,
  StatusBadge,
  type Tone,
} from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { useStrings } from "../../../i18n/hooks/useStrings";
import { DataRegion } from "../../../state/regions";
import { useHasPermission } from "../../authz/useMyPermissions";

/**
 * Portal observability (spec 025 T033): action-first overview, two-axis component health, errors with
 * acknowledge/resolve, anomalies with validate/dismiss, trends. Every status is a text label with an icon
 * (never color alone); each region loads, fails and reports "not allowed" on its own. Strings for 026.
 */
export const observabilityStrings = {
  title: "Observability",
  description: "How the portal is doing: problems first, then each component, errors, anomalies and trends.",
  component: "Component",
  count: "Seen",
  message: "Message",
  state: "State",
  severity: "Severity",
  detector: "Detector",
  info: "To know",
  run: "Run",
  done: "Done.",
  failedAction: "The action was refused.",
  errorStates: { open: "Open", acknowledged: "Acknowledged", resolved: "Resolved" } as Record<string, string>,
  overview: "Problems to look at",
  noProblems: "No problem detected.",
  portal: (status: string) => `Portal: ${status}`,
  actionNeeded: "Action needed",
  components: "Components",
  technical: "technical",
  functional: "functional",
  errors: "Errors",
  noErrors: "No error recorded.",
  acknowledge: "Acknowledge",
  resolve: "Resolve",
  resolutionField: "Resolution note",
  anomalies: "Anomalies",
  noAnomalies: "No anomaly.",
  validate: "Validate (incident)",
  dismiss: "Dismiss",
  trends: "Trends (failed jobs per day)",
  noTrend: "No data for this period.",
  diagnostics: "Diagnostics",
  logs: "Read the logs",
  states: {
    pending_validation: "To review",
    validated: "Validated",
    dismissed: "Dismissed",
    ok: "OK",
    healthy: "Healthy",
    degraded: "Degraded",
    down: "Down",
    failing: "Failing",
    unknown: "Unknown",
  } as Record<string, string>,
} as const;

/** Issue 201: the page's texts in the administrator's language (``admin:observability.*``). */
export function useObservabilityStrings() {
  return useStrings(observabilityStrings, "admin:observability", { portal: ["status"] });
}

interface Diagnostic {
  key: string;
  label: string;
  method: string;
  path: string;
  permission: string;
}

interface Problem {
  kind: string;
  id: string;
  title: string;
  action_needed: boolean;
  since: string;
  diagnostics: Diagnostic[];
}

interface ComponentHealth {
  component: string;
  technical: string;
  functional: string;
  status: string;
}

interface ErrorItem {
  id: string;
  component: string;
  category: string;
  message: string;
  count: number;
  state: string;
  last_seen_at: string;
}

interface AnomalyItem {
  id: string;
  detector: string;
  component: string;
  severity: string;
  status: string;
}

const TONE: Record<string, Tone> = {
  ok: "ok",
  healthy: "ok",
  degraded: "warn",
  down: "bad",
  failing: "bad",
  unknown: "neutral",
  open: "bad",
  acknowledged: "warn",
  resolved: "ok",
  pending_validation: "warn",
  validated: "info",
  dismissed: "neutral",
};

function StatusLabel({ state }: { state: string }) {
  const s = useObservabilityStrings();
  return (
    <StatusBadge tone={TONE[state] ?? "neutral"}>
      {s.states[state] ?? s.errorStates[state] ?? state}
    </StatusBadge>
  );
}

const unwrap = async <T,>(promise: Promise<{ data?: unknown }>): Promise<T> => (await promise).data as T;

/** Where a read-only diagnostic is shown in the portal (the API path itself is never shown). */
const DIAGNOSTIC_PAGES: Array<[string, string]> = [
  ["/api/v1/admin/events", "/admin/events"],
  ["/api/v1/services", "/admin/services"],
  ["/api/v1/admin/observability", "/admin/observability"],
];

function DiagnosticAction({ diagnostic }: { diagnostic: Diagnostic }) {
  const s = useObservabilityStrings();
  const queryClient = useQueryClient();
  const run = useMutation({
    mutationFn: () => api.POST(diagnostic.path as never, {} as never),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "observability"] }),
  });
  if (diagnostic.method === "GET") {
    const page = DIAGNOSTIC_PAGES.find(([prefix]) => diagnostic.path.startsWith(prefix))?.[1];
    return page ? (
      <Link className="ds-button ds-button--ghost" to={page}>
        {diagnostic.label}
      </Link>
    ) : null;
  }
  return (
    <>
      <Button variant="secondary" onClick={() => run.mutate()} disabled={run.isPending || run.isSuccess}>
        {diagnostic.label}
      </Button>
      {run.isSuccess ? <span role="status">{s.done}</span> : null}
      {run.isError ? <span role="alert">{s.failedAction}</span> : null}
    </>
  );
}

function Overview() {
  const s = useObservabilityStrings();
  return (
    <DataRegion<{ portal: { status: string }; problems: Problem[]; components: ComponentHealth[] }>
      label={s.overview}
      queryKey={["admin", "observability", "overview"]}
      queryFn={() => unwrap(api.GET("/api/v1/admin/observability/overview"))}
    >
      {(data) => (
        <AdminGrid>
          <AdminSection
            title={s.overview}
            icon="bell"
            flush
            actions={
              <span className="obs-portal">
                {s.portal("")}
                <StatusLabel state={data.portal.status} />
              </span>
            }
          >
            {data.problems.length === 0 ? (
              <p className="admin-muted admin-pad">{s.noProblems}</p>
            ) : (
              <ol className="admin-list" aria-label={s.overview}>
                {data.problems.map((problem) => (
                  <li key={`${problem.kind}-${problem.id}`}>
                    <StatusBadge tone={problem.action_needed ? "bad" : "neutral"}>
                      {problem.action_needed ? s.actionNeeded : s.info}
                    </StatusBadge>
                    <span className="admin-list__main">
                      <strong>{problem.title}</strong>
                      <span className="admin-muted">{new Date(problem.since).toLocaleString()}</span>
                    </span>
                    {problem.diagnostics.length > 0 ? (
                      <fieldset className="admin-list__actions obs-diagnostics" aria-label={s.diagnostics}>
                        {problem.diagnostics.map((d) => (
                          <DiagnosticAction key={d.key} diagnostic={d} />
                        ))}
                      </fieldset>
                    ) : null}
                  </li>
                ))}
              </ol>
            )}
          </AdminSection>
          <AdminSection title={s.components} icon="server" flush>
            <AdminTable<ComponentHealth>
              label={s.components}
              rows={data.components}
              rowKey={(c) => c.component}
              columns={[
                {
                  key: "component",
                  header: s.component,
                  primary: true,
                  render: (c) => c.component,
                },
                {
                  key: "technical",
                  header: s.technical,
                  render: (c) => <StatusLabel state={c.technical} />,
                },
                {
                  key: "functional",
                  header: s.functional,
                  render: (c) => <StatusLabel state={c.functional} />,
                },
              ]}
            />
          </AdminSection>
        </AdminGrid>
      )}
    </DataRegion>
  );
}

function ResolveForm({ id }: { id: string }) {
  const s = useObservabilityStrings();
  const [note, setNote] = useState("");
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: () =>
      api.POST("/api/v1/admin/observability/errors/{error_id}/resolve", {
        params: { path: { error_id: id } },
        body: { resolution: note },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "observability"] }),
  });
  function submit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }
  return (
    <form onSubmit={submit} className="admin-form obs-resolve">
      <TextField label={s.resolutionField} required value={note} onChange={(e) => setNote(e.target.value)} />
      <FormActions>
        <Button type="submit">{s.resolve}</Button>
      </FormActions>
    </form>
  );
}

function Errors() {
  const s = useObservabilityStrings();
  const queryClient = useQueryClient();
  const ack = useMutation({
    mutationFn: (id: string) =>
      api.POST("/api/v1/admin/observability/errors/{error_id}/ack", { params: { path: { error_id: id } } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "observability"] }),
  });
  return (
    <DataRegion<ErrorItem[]>
      label={s.errors}
      queryKey={["admin", "observability", "errors"]}
      queryFn={async () =>
        (await unwrap<{ items: ErrorItem[] }>(api.GET("/api/v1/admin/observability/errors"))).items
      }
    >
      {(items) => (
        <AdminTable<ErrorItem>
          label={s.errors}
          rows={items}
          rowKey={(item) => item.id}
          empty={<p className="admin-muted admin-pad">{s.noErrors}</p>}
          columns={[
            {
              key: "what",
              header: s.component,
              primary: true,
              render: (item) => (
                <span className="services-admin__name">
                  <strong>{item.category}</strong>
                  <span className="admin-muted">{item.component}</span>
                </span>
              ),
            },
            {
              key: "count",
              header: s.count,
              align: "end",
              render: (item) => `×${item.count}`,
            },
            {
              key: "message",
              header: s.message,
              render: (item) => <span className="admin-mono obs-message">{item.message}</span>,
            },
            {
              key: "state",
              header: s.state,
              render: (item) => <StatusLabel state={item.state} />,
            },
          ]}
          actions={(item) => (
            <>
              {item.state === "open" ? (
                <Button variant="secondary" onClick={() => ack.mutate(item.id)}>
                  {s.acknowledge}
                </Button>
              ) : null}
              {item.state !== "resolved" ? <ResolveForm id={item.id} /> : null}
            </>
          )}
        />
      )}
    </DataRegion>
  );
}

function Anomalies() {
  const s = useObservabilityStrings();
  const queryClient = useQueryClient();
  const decide = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "validate" | "dismiss" }) =>
      api.POST("/api/v1/admin/observability/anomalies/{anomaly_id}/{decision}", {
        params: { path: { anomaly_id: id, decision } },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "observability"] }),
  });
  return (
    <DataRegion<AnomalyItem[]>
      label={s.anomalies}
      queryKey={["admin", "observability", "anomalies"]}
      queryFn={async () =>
        (await unwrap<{ items: AnomalyItem[] }>(api.GET("/api/v1/admin/observability/anomalies"))).items
      }
    >
      {(items) => (
        <AdminTable<AnomalyItem>
          label={s.anomalies}
          rows={items}
          rowKey={(item) => item.id}
          empty={<p className="admin-muted admin-pad">{s.noAnomalies}</p>}
          columns={[
            {
              key: "what",
              header: s.component,
              primary: true,
              render: (item) => (
                <span className="services-admin__name">
                  <strong>{item.component}</strong>
                  <span className="admin-muted">{item.detector}</span>
                </span>
              ),
            },
            { key: "severity", header: s.severity, render: (item) => item.severity },
            {
              key: "status",
              header: s.state,
              render: (item) => <StatusLabel state={item.status} />,
            },
          ]}
          actions={(item) =>
            item.status === "pending_validation" ? (
              <>
                <Button
                  variant="secondary"
                  onClick={() => decide.mutate({ id: item.id, decision: "validate" })}
                >
                  {s.validate}
                </Button>
                <Button variant="ghost" onClick={() => decide.mutate({ id: item.id, decision: "dismiss" })}>
                  {s.dismiss}
                </Button>
              </>
            ) : null
          }
        />
      )}
    </DataRegion>
  );
}

function Trends() {
  const s = useObservabilityStrings();
  return (
    <DataRegion<{ points: Array<{ bucket: string; count: number }> }>
      label={s.trends}
      queryKey={["admin", "observability", "trends"]}
      queryFn={() =>
        unwrap(
          api.GET("/api/v1/admin/observability/trends", {
            params: { query: { metric: "job.failed", bucket: "day", days: 30 } },
          }),
        )
      }
    >
      {(data) => {
        if (data.points.length === 0) return <p className="admin-muted">{s.noTrend}</p>;
        const top = Math.max(1, ...data.points.map((p) => p.count));
        return (
          <ul className="obs-trend" aria-label={s.trends}>
            {data.points.map((p) => (
              <li key={p.bucket} title={`${p.bucket}: ${p.count}`}>
                <span
                  className="obs-trend__bar"
                  style={{ blockSize: `${Math.max(4, (p.count / top) * 100)}%` }}
                />
                <span className="visually-hidden">
                  {p.bucket}: {p.count}
                </span>
              </li>
            ))}
          </ul>
        );
      }}
    </DataRegion>
  );
}

export function ObservabilityAdmin() {
  const s = useObservabilityStrings();
  const logs = useHasPermission("observability.logs.read"); // issue 158
  return (
    <AdminPage
      icon="activity"
      title={s.title}
      description={s.description}
      wide
      secondary={
        logs ? (
          <Link className="ds-button ds-button--secondary" to="/admin/observability/logs">
            {s.logs}
          </Link>
        ) : undefined
      }
    >
      <Overview />
      <AdminSection title={s.errors} icon="alert" flush>
        <Errors />
      </AdminSection>
      <AdminSection title={s.anomalies} icon="gauge" flush>
        <Anomalies />
      </AdminSection>
      <AdminSection title={s.trends} icon="chart">
        <Trends />
      </AdminSection>
    </AdminPage>
  );
}
