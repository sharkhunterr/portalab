import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { api } from "../../../api/client";
import { Button } from "../../../design-system/components/Button";
import { Card } from "../../../design-system/components/Content";
import { SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { EmptyState } from "../../../design-system/components/Placeholders";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError, DataRegion } from "../../../state/regions";
import "../admin.css";

/**
 * Services administration (spec 005 T034, 027 T093): "Add a service" is the page's primary action (also
 * reachable from the Control Center with ``?add=1``) and opens a guided form — connector, name, address,
 * write-only secrets, test, save. Each configured service is a card with its state in text and its actions
 * (enable, sync, disable, disconnect with confirmation, sync history). Secrets are never displayed.
 */
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
  const t = useT();
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

  if (connectors.isPending) return null;
  if (!connectors.data || connectors.data.length === 0 || !connector) {
    return <p className="control-center__muted">{t("admin:services.noConnector")}</p>;
  }
  return (
    <form onSubmit={submit} className="services-admin__form">
      <p className="control-center__muted">{t("admin:services.wizard.intro")}</p>
      {save.isError ? <p role="alert">{t("admin:services.refused")}</p> : null}
      {save.isSuccess ? (
        <p role="status" className="services-admin__ok">
          {t("admin:services.saved")}
        </p>
      ) : null}
      {test.data ? (
        <p role="status" className={test.data.ok ? "services-admin__ok" : "services-admin__ko"}>
          {test.data.ok
            ? t("admin:services.testOk")
            : t("admin:services.testFailed", { detail: test.data.detail })}
        </p>
      ) : null}
      <SelectField
        label={t("admin:services.connector")}
        value={connector.key}
        onChange={(event) => setKey(event.target.value)}
      >
        {connectors.data.map((item) => (
          <option key={item.key} value={item.key}>
            {item.name}
          </option>
        ))}
      </SelectField>
      <TextField
        label={t("admin:services.name")}
        hint={t("admin:services.name.hint")}
        required
        value={name}
        onChange={(event) => setName(event.target.value)}
      />
      {fields.map(([field, schema]) => (
        <TextField
          key={field}
          label={schema.title ?? field}
          required={connector.config_schema.required?.includes(field) ?? false}
          value={config[field] ?? ""}
          onChange={(event) => setConfig({ ...config, [field]: event.target.value })}
        />
      ))}
      {connector.secret_fields.map((field) => (
        <TextField
          key={field}
          label={field}
          hint={t("admin:services.writeOnly.hint")}
          type="password"
          autoComplete="off"
          value={secrets[field] ?? ""}
          onChange={(event) => setSecrets({ ...secrets, [field]: event.target.value })}
        />
      ))}
      <div className="services-admin__buttons">
        <Button type="button" variant="secondary" onClick={() => test.mutate()} disabled={test.isPending}>
          <Icon name="plug" size={16} />
          {t("admin:services.test")}
        </Button>
        <Button type="submit" disabled={save.isPending}>
          <Icon name="check" size={16} />
          {t("admin:services.save")}
        </Button>
      </div>
    </form>
  );
}

function SyncHistory({ service }: { service: ServiceItem }) {
  const t = useT();
  const label = t("admin:services.historyOf", { name: service.name });
  return (
    <DataRegion<SyncRunItem[]>
      label={label}
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
          <p className="control-center__muted">{t("admin:services.noHistory")}</p>
        ) : (
          <ul aria-label={label} className="services-admin__runs">
            {runs.map((run) => (
              <li key={run.id} data-status={run.status}>
                {t("admin:services.run", {
                  kind: run.kind,
                  status: run.status,
                  added: run.added,
                  modified: run.modified,
                  removed: run.removed,
                })}
                {run.errored ? ` !${run.errored}` : ""}
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

const STATE_TONE: Record<string, string> = {
  enabled: "ok",
  syncing: "ok",
  configured: "idle",
  disabled: "idle",
  disconnected: "idle",
  maintenance: "warn",
  error: "bad",
  unavailable: "bad",
};

function ServiceCard({ service }: { service: ServiceItem }) {
  const t = useT();
  const format = useFormat();
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
      setMessage(kind === "sync" ? t("admin:services.syncQueued") : null);
      void queryClient.invalidateQueries({ queryKey: SERVICES_KEY });
    },
    onError: (error) => setMessage(error instanceof ApiError ? error.message : t("admin:services.refused")),
  });
  const state = t(`admin:services.state.${service.display_state}`);
  const active = ["enabled", "error", "unavailable", "maintenance"].includes(service.state);
  const last = service.sync.last_success_at;
  const since = last ? (Date.parse(last) - Date.now()) / 1000 : null;
  return (
    <Card
      className="services-admin__card"
      data-tone={STATE_TONE[service.display_state] ?? "idle"}
      title={service.name}
      icon="server"
      actions={<span className="ds-badge services-admin__state">{state}</span>}
    >
      <p className="control-center__muted">
        {service.connector} ·{" "}
        {since !== null && !Number.isNaN(since)
          ? t("admin:services.lastSuccess", { when: format.relative(since) })
          : t("admin:services.never")}
      </p>
      {message ? <p role="status">{message}</p> : null}
      <div className="services-admin__buttons">
        {service.state === "configured" || service.state === "disabled" ? (
          <Button type="button" onClick={() => action.mutate("enable")}>
            {t("admin:services.enable")}
          </Button>
        ) : null}
        {active ? (
          <>
            <Button type="button" variant="secondary" onClick={() => action.mutate("sync")}>
              <Icon name="sync" size={16} />
              {t("admin:services.syncNow")}
            </Button>
            <Button type="button" variant="ghost" onClick={() => action.mutate("disable")}>
              {t("admin:services.disable")}
            </Button>
          </>
        ) : null}
        {service.state !== "disconnected" ? (
          confirming ? (
            <Button type="button" variant="danger" onClick={() => action.mutate("disconnect")}>
              {t("admin:services.confirmDisconnect")}
            </Button>
          ) : (
            <Button type="button" variant="ghost" onClick={() => setConfirming(true)}>
              {t("admin:services.disconnect")}
            </Button>
          )
        ) : null}
        <Button
          type="button"
          variant="ghost"
          aria-expanded={showHistory}
          onClick={() => setShowHistory(!showHistory)}
        >
          <Icon name="clock" size={16} />
          {t("admin:services.history")}
        </Button>
      </div>
      {showHistory ? <SyncHistory service={service} /> : null}
    </Card>
  );
}

export function ServicesAdmin() {
  const t = useT();
  const [params, setParams] = useSearchParams();
  const [open, setOpen] = useState(params.get("add") === "1");
  function toggle(next: boolean) {
    setOpen(next);
    if (!next && params.has("add")) {
      params.delete("add");
      setParams(params, { replace: true });
    }
  }
  const addButton = (
    <Button type="button">
      <Icon name="plus" size={18} />
      {t("admin:services.add")}
    </Button>
  );
  return (
    <div className="services-admin">
      <PageHeader
        level={2}
        icon="plug"
        title={t("admin:services.title")}
        context={t("admin:services.subtitle")}
        secondary={
          <Link className="ds-button ds-button--ghost" to="/services">
            {t("admin:services.status")}
          </Link>
        }
        primary={
          <Dialog
            open={open}
            onOpenChange={toggle}
            title={t("admin:services.wizard.title")}
            trigger={addButton}
          >
            <ConfigureService />
          </Dialog>
        }
      />
      <DataRegion<ServiceItem[]>
        label={t("admin:services.list")}
        queryKey={SERVICES_KEY}
        queryFn={async () => (await unwrap<{ items: ServiceItem[] }>(api.GET("/api/v1/services"))).items}
      >
        {(services) =>
          services.length === 0 ? (
            <EmptyState
              icon="server"
              title={t("admin:services.empty.title")}
              message={t("admin:services.empty.message")}
              action={{ label: t("admin:services.add"), onSelect: () => toggle(true) }}
            />
          ) : (
            <ul aria-label={t("admin:services.list")} className="services-admin__list">
              {services.map((service) => (
                <li key={service.id}>
                  <ServiceCard service={service} />
                </li>
              ))}
            </ul>
          )
        }
      </DataRegion>
    </div>
  );
}
