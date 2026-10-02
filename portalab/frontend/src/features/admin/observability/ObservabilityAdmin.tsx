import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { api } from "../../../api/client";
import { DataRegion } from "../../../state/regions";

/**
 * Portal observability (spec 025 T033): action-first overview, two-axis component health, errors with
 * acknowledge/resolve, anomalies with validate/dismiss, trends. Every status is a text label with an icon
 * (never color alone); each region loads, fails and reports "not allowed" on its own. Strings for 026.
 */
export const observabilityStrings = {
  title: "Observability",
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
  states: {
    ok: "OK",
    healthy: "Healthy",
    degraded: "Degraded",
    down: "Down",
    failing: "Failing",
    unknown: "Unknown",
  } as Record<string, string>,
} as const;

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

const MARK: Record<string, string> = {
  ok: "✓",
  healthy: "✓",
  degraded: "◐",
  down: "✕",
  failing: "✕",
  unknown: "?",
};

function StatusLabel({ state }: { state: string }) {
  return (
    <span className={`obs-status obs-status--${state}`} data-state={state}>
      <span aria-hidden="true">{MARK[state] ?? "?"}</span> {observabilityStrings.states[state] ?? state}
    </span>
  );
}

const unwrap = async <T,>(promise: Promise<{ data?: unknown }>): Promise<T> => (await promise).data as T;

function Overview() {
  return (
    <DataRegion<{ portal: { status: string }; problems: Problem[]; components: ComponentHealth[] }>
      label={observabilityStrings.overview}
      queryKey={["admin", "observability", "overview"]}
      queryFn={() => unwrap(api.GET("/api/v1/admin/observability/overview"))}
    >
      {(data) => (
        <>
          <p>
            {observabilityStrings.portal("")}
            <StatusLabel state={data.portal.status} />
          </p>
          <h3>{observabilityStrings.overview}</h3>
          {data.problems.length === 0 ? (
            <p>{observabilityStrings.noProblems}</p>
          ) : (
            <ol aria-label={observabilityStrings.overview}>
              {data.problems.map((problem) => (
                <li key={`${problem.kind}-${problem.id}`}>
                  {problem.action_needed ? <strong>{observabilityStrings.actionNeeded}: </strong> : null}
                  {problem.title}
                  {problem.diagnostics.length > 0 ? (
                    <ul aria-label={observabilityStrings.diagnostics}>
                      {problem.diagnostics.map((d) => (
                        <li key={d.key}>
                          {d.label} <code>{`${d.method} ${d.path}`}</code>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              ))}
            </ol>
          )}
          <h3>{observabilityStrings.components}</h3>
          <table>
            <caption>{observabilityStrings.components}</caption>
            <thead>
              <tr>
                <th scope="col">Component</th>
                <th scope="col">{observabilityStrings.technical}</th>
                <th scope="col">{observabilityStrings.functional}</th>
              </tr>
            </thead>
            <tbody>
              {data.components.map((c) => (
                <tr key={c.component}>
                  <th scope="row">{c.component}</th>
                  <td>
                    <StatusLabel state={c.technical} />
                  </td>
                  <td>
                    <StatusLabel state={c.functional} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </DataRegion>
  );
}

function ResolveForm({ id }: { id: string }) {
  const fieldId = useId();
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
    <form onSubmit={submit}>
      <label htmlFor={fieldId}>{observabilityStrings.resolutionField}</label>
      <input id={fieldId} required value={note} onChange={(event) => setNote(event.target.value)} />
      <button type="submit">{observabilityStrings.resolve}</button>
    </form>
  );
}

function Errors() {
  const queryClient = useQueryClient();
  const ack = useMutation({
    mutationFn: (id: string) =>
      api.POST("/api/v1/admin/observability/errors/{error_id}/ack", { params: { path: { error_id: id } } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "observability"] }),
  });
  return (
    <DataRegion<ErrorItem[]>
      label={observabilityStrings.errors}
      queryKey={["admin", "observability", "errors"]}
      queryFn={async () =>
        (await unwrap<{ items: ErrorItem[] }>(api.GET("/api/v1/admin/observability/errors"))).items
      }
    >
      {(items) =>
        items.length === 0 ? (
          <p>{observabilityStrings.noErrors}</p>
        ) : (
          <ul aria-label={observabilityStrings.errors}>
            {items.map((item) => (
              <li key={item.id}>
                {item.component} · {item.category} ×{item.count} — {item.message} ({item.state})
                {item.state === "open" ? (
                  <button type="button" onClick={() => ack.mutate(item.id)}>
                    {observabilityStrings.acknowledge}
                  </button>
                ) : null}
                {item.state !== "resolved" ? <ResolveForm id={item.id} /> : null}
              </li>
            ))}
          </ul>
        )
      }
    </DataRegion>
  );
}

function Anomalies() {
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
      label={observabilityStrings.anomalies}
      queryKey={["admin", "observability", "anomalies"]}
      queryFn={async () =>
        (await unwrap<{ items: AnomalyItem[] }>(api.GET("/api/v1/admin/observability/anomalies"))).items
      }
    >
      {(items) =>
        items.length === 0 ? (
          <p>{observabilityStrings.noAnomalies}</p>
        ) : (
          <ul aria-label={observabilityStrings.anomalies}>
            {items.map((item) => (
              <li key={item.id}>
                {item.detector} · {item.component} · {item.severity} · {item.status}
                {item.status === "pending_validation" ? (
                  <>
                    <button
                      type="button"
                      onClick={() => decide.mutate({ id: item.id, decision: "validate" })}
                    >
                      {observabilityStrings.validate}
                    </button>
                    <button type="button" onClick={() => decide.mutate({ id: item.id, decision: "dismiss" })}>
                      {observabilityStrings.dismiss}
                    </button>
                  </>
                ) : null}
              </li>
            ))}
          </ul>
        )
      }
    </DataRegion>
  );
}

function Trends() {
  return (
    <DataRegion<{ points: Array<{ bucket: string; count: number }> }>
      label={observabilityStrings.trends}
      queryKey={["admin", "observability", "trends"]}
      queryFn={() =>
        unwrap(
          api.GET("/api/v1/admin/observability/trends", {
            params: { query: { metric: "job.failed", bucket: "day", days: 30 } },
          }),
        )
      }
    >
      {(data) =>
        data.points.length === 0 ? (
          <p>{observabilityStrings.noTrend}</p>
        ) : (
          <ul aria-label={observabilityStrings.trends}>
            {data.points.map((p) => (
              <li key={p.bucket}>
                {p.bucket}: {p.count}
              </li>
            ))}
          </ul>
        )
      }
    </DataRegion>
  );
}

export function ObservabilityAdmin() {
  return (
    <div className="account-page">
      <h2>{observabilityStrings.title}</h2>
      <Overview />
      <h3>{observabilityStrings.errors}</h3>
      <Errors />
      <h3>{observabilityStrings.anomalies}</h3>
      <Anomalies />
      <h3>{observabilityStrings.trends}</h3>
      <Trends />
    </div>
  );
}
