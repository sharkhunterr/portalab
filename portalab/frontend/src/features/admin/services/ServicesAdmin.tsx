import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { api } from "../../../api/client";
import { ApiError, DataRegion } from "../../../state/regions";

/**
 * Services administration (spec 005 T034): list, configure + test, enable/disable/disconnect, sync now and
 * sync history. Secrets are write-only (password inputs, never displayed). Strings are externalized for 026.
 */
export const servicesStrings = {
  title: "Services",
  list: "Configured services",
  empty: "No service is configured yet.",
  configureTitle: "Add a service",
  connectorField: "Connector",
  nameField: "Name",
  secretSet: "set",
  test: "Test the connection",
  save: "Save",
  saved: "Service saved. Enable it once the test passes.",
  testOk: "Connection succeeded.",
  testFailed: (detail: string) => `Connection failed: ${detail}`,
  enable: "Enable",
  disable: "Disable",
  disconnect: "Disconnect",
  confirmDisconnect: "Confirm disconnection (data is kept)",
  syncNow: "Sync now",
  syncQueued: "Synchronization queued.",
  history: "Sync history",
  noHistory: "No synchronization yet.",
  historyOf: (name: string) => `Sync history of ${name}`,
  state: {
    configured: "Configured",
    enabled: "Enabled",
    syncing: "Syncing",
    error: "Error",
    unavailable: "Unavailable",
    maintenance: "Maintenance",
    disabled: "Disabled",
    disconnected: "Disconnected (historical)",
  } as Record<string, string>,
  lastSuccess: (at: string | null) => (at ? `last success ${at}` : "never synchronized"),
  run: (run: SyncRunItem) =>
    `${run.kind} · ${run.status} · +${run.added} ~${run.modified} -${run.removed}${run.errored ? ` !${run.errored}` : ""}`,
  genericError: "The operation was refused.",
} as const;

interface ConnectorItem {
  key: string;
  name: string;
  secret_fields: string[];
  config_schema: { properties?: Record<string, { type?: string; title?: string }>; required?: string[] };
  compatibility: { result: string; reasons: string[] };
}

interface ServiceItem {
  id: string;
  connector: string;
  name: string;
  state: string;
  display_state: string;
  health: string;
  stale: boolean;
  secrets_set?: string[];
  sync: { status: string; last_success_at: string | null };
}

interface SyncRunItem {
  id: string;
  kind: string;
  status: string;
  added: number;
  modified: number;
  removed: number;
  errored: number;
  last_error: string | null;
}

interface TestOutcome {
  ok: boolean;
  detail: string;
}

const SERVICES_KEY = ["admin", "services"] as const;

async function unwrap<T>(promise: Promise<{ data?: unknown }>): Promise<T> {
  return (await promise).data as T;
}

function ConfigureService() {
  const ids = { title: useId(), connector: useId(), name: useId(), prefix: useId() };
  const queryClient = useQueryClient();
  const connectors = useQuery({
    queryKey: ["admin", "connectors"],
    queryFn: async () => (await unwrap<{ items: ConnectorItem[] }>(api.GET("/api/v1/connectors"))).items,
  });
  const [key, setKey] = useState("");
  const [name, setName] = useState("");
  const [config, setConfig] = useState<Record<string, string>>({});
  const [secrets, setSecrets] = useState<Record<string, string>>({});
  const connector = connectors.data?.find((item) => item.key === key) ?? connectors.data?.[0];
  const fields = Object.entries(connector?.config_schema.properties ?? {}).filter(
    ([, schema]) => schema.type === "string",
  );

  const test = useMutation({
    mutationFn: async () =>
      unwrap<TestOutcome>(
        api.POST("/api/v1/connectors/{key}/test", {
          params: { path: { key: connector?.key ?? "" } },
          body: { config, secrets },
        }),
      ),
  });
  const save = useMutation({
    mutationFn: async () =>
      unwrap<ServiceItem>(
        api.POST("/api/v1/services", { body: { connector: connector?.key ?? "", name, config, secrets } }),
      ),
    onSuccess: () => {
      setSecrets({});
      void queryClient.invalidateQueries({ queryKey: SERVICES_KEY });
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate();
  }

  if (!connectors.data || connectors.data.length === 0 || !connector) {
    return null;
  }
  return (
    <form onSubmit={submit} aria-labelledby={ids.title} className="auth-form">
      <h3 id={ids.title}>{servicesStrings.configureTitle}</h3>
      {save.isError ? <p role="alert">{servicesStrings.genericError}</p> : null}
      {save.isSuccess ? <p role="status">{servicesStrings.saved}</p> : null}
      {test.data ? (
        <p role="status">
          {test.data.ok ? servicesStrings.testOk : servicesStrings.testFailed(test.data.detail)}
        </p>
      ) : null}
      <label htmlFor={ids.connector}>{servicesStrings.connectorField}</label>
      <select id={ids.connector} value={connector.key} onChange={(event) => setKey(event.target.value)}>
        {connectors.data.map((item) => (
          <option key={item.key} value={item.key}>
            {item.name}
          </option>
        ))}
      </select>
      <label htmlFor={ids.name}>{servicesStrings.nameField}</label>
      <input id={ids.name} required value={name} onChange={(event) => setName(event.target.value)} />
      {fields.map(([field, schema]) => (
        <div key={field}>
          <label htmlFor={`${ids.prefix}-${field}`}>{schema.title ?? field}</label>
          <input
            id={`${ids.prefix}-${field}`}
            required={connector.config_schema.required?.includes(field) ?? false}
            value={config[field] ?? ""}
            onChange={(event) => setConfig({ ...config, [field]: event.target.value })}
          />
        </div>
      ))}
      {connector.secret_fields.map((field) => (
        <div key={field}>
          <label htmlFor={`${ids.prefix}-secret-${field}`}>{field}</label>
          <input
            id={`${ids.prefix}-secret-${field}`}
            type="password"
            autoComplete="off"
            value={secrets[field] ?? ""}
            onChange={(event) => setSecrets({ ...secrets, [field]: event.target.value })}
          />
        </div>
      ))}
      <button type="button" onClick={() => test.mutate()} disabled={test.isPending}>
        {servicesStrings.test}
      </button>
      <button type="submit" disabled={save.isPending}>
        {servicesStrings.save}
      </button>
    </form>
  );
}

function SyncHistory({ service }: { service: ServiceItem }) {
  return (
    <DataRegion<SyncRunItem[]>
      label={servicesStrings.historyOf(service.name)}
      queryKey={[...SERVICES_KEY, service.id, "runs"]}
      queryFn={async () =>
        (
          await unwrap<{ items: SyncRunItem[] }>(
            api.GET("/api/v1/services/{service_id}/sync-runs", {
              params: { path: { service_id: service.id } },
            }),
          )
        ).items
      }
    >
      {(runs) =>
        runs.length === 0 ? (
          <p>{servicesStrings.noHistory}</p>
        ) : (
          <ul aria-label={servicesStrings.historyOf(service.name)}>
            {runs.map((run) => (
              <li key={run.id}>
                {servicesStrings.run(run)}
                {run.last_error ? ` — ${run.last_error}` : ""}
              </li>
            ))}
          </ul>
        )
      }
    </DataRegion>
  );
}

type Action = "enable" | "disable" | "disconnect" | "sync";

function ServiceRow({ service }: { service: ServiceItem }) {
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const action = useMutation({
    mutationFn: async (kind: Action) => {
      const params = { params: { path: { service_id: service.id } } };
      if (kind === "sync") return api.POST("/api/v1/services/{service_id}/sync", params);
      if (kind === "enable") return api.POST("/api/v1/services/{service_id}/enable", params);
      if (kind === "disable") return api.POST("/api/v1/services/{service_id}/disable", params);
      return api.POST("/api/v1/services/{service_id}/disconnect", params);
    },
    onSuccess: (_, kind) => {
      setConfirming(false);
      setMessage(kind === "sync" ? servicesStrings.syncQueued : null);
      void queryClient.invalidateQueries({ queryKey: SERVICES_KEY });
    },
    onError: (error) => setMessage(error instanceof ApiError ? error.message : servicesStrings.genericError),
  });
  const state = servicesStrings.state[service.display_state] ?? service.display_state;
  const active = ["enabled", "error", "unavailable", "maintenance"].includes(service.state);
  return (
    <li>
      <strong>{service.name}</strong> · {service.connector} · {state} ·{" "}
      {servicesStrings.lastSuccess(service.sync.last_success_at)}
      {message ? <span role="status"> {message}</span> : null}
      <div>
        {service.state === "configured" || service.state === "disabled" ? (
          <button type="button" onClick={() => action.mutate("enable")}>
            {servicesStrings.enable}
          </button>
        ) : null}
        {active ? (
          <>
            <button type="button" onClick={() => action.mutate("sync")}>
              {servicesStrings.syncNow}
            </button>
            <button type="button" onClick={() => action.mutate("disable")}>
              {servicesStrings.disable}
            </button>
          </>
        ) : null}
        {service.state !== "disconnected" ? (
          confirming ? (
            <button type="button" onClick={() => action.mutate("disconnect")}>
              {servicesStrings.confirmDisconnect}
            </button>
          ) : (
            <button type="button" onClick={() => setConfirming(true)}>
              {servicesStrings.disconnect}
            </button>
          )
        ) : null}
        <button type="button" aria-expanded={showHistory} onClick={() => setShowHistory(!showHistory)}>
          {servicesStrings.history}
        </button>
      </div>
      {showHistory ? <SyncHistory service={service} /> : null}
    </li>
  );
}

export function ServicesAdmin() {
  return (
    <div className="account-page">
      <h2>{servicesStrings.title}</h2>
      <DataRegion<ServiceItem[]>
        label={servicesStrings.list}
        queryKey={SERVICES_KEY}
        queryFn={async () => (await unwrap<{ items: ServiceItem[] }>(api.GET("/api/v1/services"))).items}
      >
        {(services) =>
          services.length === 0 ? (
            <p>{servicesStrings.empty}</p>
          ) : (
            <ul aria-label={servicesStrings.list}>
              {services.map((service) => (
                <ServiceRow key={service.id} service={service} />
              ))}
            </ul>
          )
        }
      </DataRegion>
      <ConfigureService />
    </div>
  );
}
