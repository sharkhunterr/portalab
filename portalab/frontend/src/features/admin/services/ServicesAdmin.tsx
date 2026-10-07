import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { api } from "../../../api/client";
import {
  AdminEmpty,
  AdminPage,
  AdminSection,
  AdminStats,
  AdminTable,
  FormActions,
  FormGrid,
  LiveProgress,
  StatusBadge,
  type Tone,
} from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { useFormat } from "../../../i18n/format/useFormat";
import { type Translate, useT } from "../../../i18n/hooks/useT";
import { ApiError, DataRegion } from "../../../state/regions";
import "../admin.css";

/**
 * Services administration (spec 005 T034, 027 T093) on the administration kit: key figures, one table row
 * per configured service (state in text, last synchronization, actions) and "Add a service" as the primary
 * action (also reachable with ``?add=1``) — a two-step wizard: choose the kind of service among the
 * installed connectors (Jellyfin, Plex, Seerr, Radarr, Sonarr, RomM, plugins…), then fill its address and
 * credentials with a hint telling where to find them, test, save and enable. Secrets are write-only.
 */
interface ConnectorItem {
  key: string;
  name: string;
  description?: string;
  icon?: string;
  category?: string;
  secret_fields: string[];
  config_schema: {
    properties?: Record<string, { type?: string; title?: string; description?: string; default?: unknown }>;
    required?: string[];
  };
  compatibility: { result: string; reasons: string[] };
  provides?: string[];
  /** 027: capabilities « sync now » runs; an empty list means the service is read continuously. */
  syncable?: string[];
}

/** Read continuously (history every few minutes, metadata enrichment…): nothing for « sync now » to do. */
function continuous(connector: ConnectorItem | undefined): boolean {
  return Boolean(connector?.syncable && connector.syncable.length === 0);
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
  public_url?: string | null;
  config?: Record<string, unknown>;
  sync_interval_seconds?: number | null;
  sync: {
    status: string;
    last_success_at: string | null;
    progress?: { capability: string; done: number; total: number | null; started_at: string } | null;
  };
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
/** When a sync was last asked for: the list refreshes quickly until it shows up as running (027). */
let syncRequestedAt = 0;

function pollServices(services: ServiceItem[] | undefined): number | false {
  const running = (services ?? []).some((s) => s.sync.status === "running");
  return running || Date.now() - syncRequestedAt < 20_000 ? 2000 : false;
}
/** Catalog entry naming each kind of write-only credential field (catalog keys never name secrets). */
const ACCESS_LABELS: Record<string, string> = {
  api_key: "app",
  token: "plex",
  password: "account",
  api_token: "generic",
};
const STATE_TONE: Record<string, Tone> = {
  enabled: "ok",
  syncing: "info",
  configured: "neutral",
  disabled: "neutral",
  disconnected: "neutral",
  maintenance: "warn",
  error: "bad",
  unavailable: "bad",
};

async function unwrap<T>(promise: Promise<{ data?: unknown }>): Promise<T> {
  return (await promise).data as T;
}

/** A translated text when the catalog has one, else the fallback (connectors added by plugins). */
function maybe(t: Translate, key: string, fallback: string): string {
  const text = t(key);
  return text === key.split(":").slice(1).join(":") ? fallback : text;
}

function useConnectors() {
  return useQuery({
    queryKey: ["admin", "connectors"],
    queryFn: async () => (await unwrap<{ items: ConnectorItem[] }>(api.GET("/api/v1/connectors"))).items,
  });
}

function ConnectorPicker({
  connectors,
  onPick,
}: {
  connectors: ConnectorItem[];
  onPick: (connector: ConnectorItem) => void;
}) {
  const t = useT();
  return (
    <ul className="connector-picker" aria-label={t("admin:services.connector")}>
      {connectors.map((connector) => (
        <li key={connector.key}>
          <button type="button" className="connector-card" onClick={() => onPick(connector)}>
            <span className="connector-card__icon" aria-hidden="true">
              <Icon name={connector.icon ?? "server"} size={24} />
            </span>
            <span className="connector-card__text">
              <strong>{connector.name}</strong>
              <span>
                {maybe(
                  t,
                  `admin:services.connector.${connector.key}.description`,
                  connector.description ?? "",
                )}
              </span>
            </span>
            {connector.category ? (
              <span className="ds-badge">
                {maybe(t, `admin:services.category.${connector.category}`, connector.category)}
              </span>
            ) : null}
          </button>
        </li>
      ))}
    </ul>
  );
}

function ConfigureService({ connector, onBack }: { connector: ConnectorItem; onBack: () => void }) {
  const t = useT();
  const queryClient = useQueryClient();
  const fields = Object.entries(connector.config_schema.properties ?? {});
  const [name, setName] = useState(connector.name.split(" (")[0] ?? connector.name);
  const [config, setConfig] = useState<Record<string, unknown>>(() =>
    Object.fromEntries(fields.filter(([, s]) => s.default !== undefined).map(([k, s]) => [k, s.default])),
  );
  const [secrets, setSecrets] = useState<Record<string, string>>({});
  const [created, setCreated] = useState<ServiceItem | null>(null);

  const test = useMutation({
    mutationFn: async () =>
      unwrap<TestOutcome>(
        api.POST("/api/v1/connectors/{key}/test", {
          params: { path: { key: connector.key } },
          body: { config, secrets },
        }),
      ),
  });
  const save = useMutation({
    mutationFn: async () =>
      unwrap<ServiceItem>(
        api.POST("/api/v1/services", { body: { connector: connector.key, name, config, secrets } }),
      ),
    onSuccess: (service) => {
      setSecrets({});
      setCreated(service);
      void queryClient.invalidateQueries({ queryKey: SERVICES_KEY });
    },
  });
  const enable = useMutation({
    mutationFn: async (serviceId: string) => {
      await api.POST("/api/v1/services/{service_id}/enable", { params: { path: { service_id: serviceId } } });
      await api.POST("/api/v1/services/{service_id}/sync", { params: { path: { service_id: serviceId } } });
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: SERVICES_KEY }),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate();
  }

  const help = maybe(t, `admin:services.connector.${connector.key}.help`, "");
  return (
    <form onSubmit={submit} className="services-admin__form">
      <div className="services-admin__chosen">
        <span className="connector-card__icon" aria-hidden="true">
          <Icon name={connector.icon ?? "server"} size={22} />
        </span>
        <strong>{connector.name}</strong>
        {!created ? (
          <Button type="button" variant="ghost" onClick={onBack}>
            <Icon name="chevron-left" size={16} />
            {t("admin:services.otherKind")}
          </Button>
        ) : null}
      </div>
      {help ? (
        <p className="services-admin__help">
          <Icon name="lightbulb" size={16} />
          {help}
        </p>
      ) : null}
      <FormGrid>
        <TextField
          label={t("admin:services.name")}
          hint={t("admin:services.name.hint")}
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        {fields.map(([field, schema]) => {
          const label = maybe(t, `admin:services.field.${field}`, schema.title ?? field);
          if (schema.type === "boolean") {
            return (
              <CheckboxField
                key={field}
                label={label}
                checked={Boolean(config[field] ?? true)}
                onChange={(event) => setConfig({ ...config, [field]: event.target.checked })}
              />
            );
          }
          return (
            <TextField
              key={field}
              label={label}
              hint={maybe(t, `admin:services.field.${field}.hint`, schema.description ?? "") || undefined}
              required={connector.config_schema.required?.includes(field) ?? false}
              inputMode={field === "base_url" ? "url" : undefined}
              placeholder={field === "base_url" ? "http://192.168.1.10:8096" : undefined}
              value={String(config[field] ?? "")}
              onChange={(event) => setConfig({ ...config, [field]: event.target.value })}
            />
          );
        })}
        {connector.secret_fields.map((field) => (
          <TextField
            key={field}
            label={maybe(t, `admin:services.access.${ACCESS_LABELS[field] ?? field}`, field)}
            hint={t("admin:services.writeOnly.hint")}
            type="password"
            autoComplete="off"
            value={secrets[field] ?? ""}
            onChange={(event) => setSecrets({ ...secrets, [field]: event.target.value })}
          />
        ))}
      </FormGrid>
      {save.isError ? (
        <p role="alert" className="services-admin__ko">
          {save.error instanceof ApiError ? save.error.message : t("admin:services.refused")}
        </p>
      ) : null}
      {test.data ? (
        <p role="status" className={test.data.ok ? "services-admin__ok" : "services-admin__ko"}>
          {test.data.ok
            ? t("admin:services.testOk")
            : t("admin:services.testFailed", { detail: test.data.detail })}
        </p>
      ) : null}
      {created ? (
        <div role="status" className="services-admin__ok services-admin__done">
          <span>{t("admin:services.saved")}</span>
          {enable.isSuccess ? (
            <strong>{t("admin:services.enabledSyncing")}</strong>
          ) : (
            <Button type="button" onClick={() => enable.mutate(created.id)} disabled={enable.isPending}>
              <Icon name="zap" size={16} />
              {t("admin:services.enableNow")}
            </Button>
          )}
          {enable.isError ? <span role="alert">{t("admin:services.refused")}</span> : null}
        </div>
      ) : (
        <FormActions>
          <Button type="button" variant="secondary" onClick={() => test.mutate()} disabled={test.isPending}>
            <Icon name="plug" size={16} />
            {t("admin:services.test")}
          </Button>
          <Button type="submit" disabled={save.isPending}>
            <Icon name="check" size={16} />
            {t("admin:services.save")}
          </Button>
        </FormActions>
      )}
    </form>
  );
}

function AddServiceWizard() {
  const t = useT();
  const connectors = useConnectors();
  const [chosen, setChosen] = useState<ConnectorItem | null>(null);
  if (connectors.isPending) return <p className="admin-muted">…</p>;
  const usable = (connectors.data ?? []).filter((c) => c.compatibility.result !== "incompatible");
  if (!usable.length) {
    return (
      <AdminEmpty
        icon="plug"
        title={t("admin:services.noConnector")}
        action={
          <Link className="ds-button ds-button--primary" to="/admin/plugins">
            {t("admin:services.toPlugins")}
          </Link>
        }
      />
    );
  }
  if (!chosen) {
    return (
      <>
        <p className="admin-muted">{t("admin:services.wizard.pick")}</p>
        <ConnectorPicker connectors={usable} onPick={setChosen} />
      </>
    );
  }
  return <ConfigureService key={chosen.key} connector={chosen} onBack={() => setChosen(null)} />;
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
          <p className="admin-muted">{t("admin:services.noHistory")}</p>
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

/** The address members open the service at (027: the quick-access widget). */
/**
 * 027: edit a configured service — its name, address and settings, its secrets (write-only: left empty,
 * a secret is kept), where members open it and how often it syncs. « Test » checks the edited values
 * before saving; the background worker picks the change up within a minute.
 */
function EditService({
  service,
  connector,
}: {
  service: ServiceItem;
  connector?: ConnectorItem | undefined;
}) {
  const t = useT();
  const queryClient = useQueryClient();
  const fields = Object.entries(connector?.config_schema.properties ?? {});
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(service.name);
  const [config, setConfig] = useState<Record<string, unknown>>(service.config ?? {});
  const [secrets, setSecrets] = useState<Record<string, string>>({});
  const [publicUrl, setPublicUrl] = useState(service.public_url ?? "");
  const [every, setEvery] = useState(
    service.sync_interval_seconds ? String(Math.round(service.sync_interval_seconds / 60)) : "",
  );
  const filled = Object.fromEntries(Object.entries(secrets).filter(([, v]) => v.trim()));
  const test = useMutation({
    mutationFn: async () =>
      unwrap<TestOutcome>(
        api.POST("/api/v1/services/{service_id}/test", {
          params: { path: { service_id: service.id } },
          body: { config, secrets: filled },
        }),
      ),
  });
  const save = useMutation({
    mutationFn: async () =>
      unwrap<ServiceItem>(
        api.PATCH("/api/v1/services/{service_id}", {
          params: { path: { service_id: service.id } },
          body: {
            name: name.trim(),
            config,
            ...(Object.keys(filled).length ? { secrets: filled } : {}),
            public_url: publicUrl.trim(),
            sync_interval_seconds: every.trim() ? Math.max(0, Number(every)) * 60 : 0,
          },
        }),
      ),
    onSuccess: () => {
      setOpen(false);
      setSecrets({});
      void queryClient.invalidateQueries({ queryKey: SERVICES_KEY });
    },
  });
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) {
          setName(service.name);
          setConfig(service.config ?? {});
          setSecrets({});
          setPublicUrl(service.public_url ?? "");
          setEvery(
            service.sync_interval_seconds ? String(Math.round(service.sync_interval_seconds / 60)) : "",
          );
          test.reset();
          save.reset();
        }
      }}
      size="lg"
      title={t("admin:services.edit.title", { name: service.name })}
      closeLabel={t("admin:services.close")}
      trigger={
        <Button type="button" variant="ghost">
          <Icon name="settings" size={16} />
          {t("admin:services.edit")}
        </Button>
      }
    >
      <form
        className="services-admin__form"
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate();
        }}
      >
        <FormGrid>
          <TextField
            label={t("admin:services.name")}
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          {fields.map(([field, schema]) => {
            const label = maybe(t, `admin:services.field.${field}`, schema.title ?? field);
            if (schema.type === "boolean") {
              return (
                <CheckboxField
                  key={field}
                  label={label}
                  checked={Boolean(config[field] ?? true)}
                  onChange={(event) => setConfig({ ...config, [field]: event.target.checked })}
                />
              );
            }
            return (
              <TextField
                key={field}
                label={label}
                hint={maybe(t, `admin:services.field.${field}.hint`, schema.description ?? "") || undefined}
                required={connector?.config_schema.required?.includes(field) ?? false}
                inputMode={field === "base_url" ? "url" : undefined}
                value={String(config[field] ?? "")}
                onChange={(event) => setConfig({ ...config, [field]: event.target.value })}
              />
            );
          })}
          {(connector?.secret_fields ?? []).map((field) => (
            <TextField
              key={field}
              label={maybe(t, `admin:services.access.${ACCESS_LABELS[field] ?? field}`, field)}
              hint={
                service.secrets_set?.includes(field)
                  ? t("admin:services.edit.secretKept")
                  : t("admin:services.writeOnly.hint")
              }
              type="password"
              autoComplete="off"
              value={secrets[field] ?? ""}
              onChange={(event) => setSecrets({ ...secrets, [field]: event.target.value })}
            />
          ))}
          <TextField
            label={t("admin:services.link.field")}
            hint={t("admin:services.link.hint")}
            inputMode="url"
            type="url"
            placeholder="https://plex.example.org"
            value={publicUrl}
            onChange={(event) => setPublicUrl(event.target.value)}
          />
          <TextField
            label={t("admin:services.edit.interval")}
            hint={t("admin:services.edit.intervalHint")}
            type="number"
            min={0}
            max={10080}
            value={every}
            onChange={(event) => setEvery(event.target.value)}
          />
        </FormGrid>
        {test.data ? (
          <p role="status" className={test.data.ok ? "services-admin__ok" : "services-admin__ko"}>
            {test.data.ok
              ? t("admin:services.testOk")
              : t("admin:services.testFailed", { detail: test.data.detail })}
          </p>
        ) : null}
        {save.isError ? (
          <p role="alert" className="services-admin__ko">
            {save.error instanceof ApiError ? save.error.message : t("admin:services.refused")}
          </p>
        ) : null}
        <FormActions>
          <Button type="button" variant="secondary" onClick={() => test.mutate()} disabled={test.isPending}>
            <Icon name={test.isPending ? "spinner" : "plug"} size={16} />
            {t("admin:services.test")}
          </Button>
          <Button type="submit" disabled={save.isPending || !name.trim()}>
            <Icon name="check" size={16} />
            {t("admin:services.edit.save")}
          </Button>
        </FormActions>
      </form>
    </Dialog>
  );
}

function ServiceActions({
  service,
  connector,
}: {
  service: ServiceItem;
  connector?: ConnectorItem | undefined;
}) {
  const t = useT();
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const action = useMutation({
    mutationFn: async (kind: Action) => {
      const params = { params: { path: { service_id: service.id } } };
      if (kind === "sync") {
        syncRequestedAt = Date.now();
        return api.POST("/api/v1/services/{service_id}/sync", params);
      }
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
  const active = ["enabled", "error", "unavailable", "maintenance"].includes(service.state);
  return (
    <>
      {message ? (
        <span role="status" className="admin-muted">
          {message}
        </span>
      ) : null}
      {service.state === "configured" || service.state === "disabled" ? (
        <Button type="button" onClick={() => action.mutate("enable")}>
          {t("admin:services.enable")}
        </Button>
      ) : null}
      {active ? (
        <>
          {continuous(connector) ? (
            <Link className="ds-button ds-button--secondary" to="/admin/media-sources">
              <Icon name="chart" size={16} />
              {t("admin:services.followUp")}
            </Link>
          ) : (
            <Button type="button" variant="secondary" onClick={() => action.mutate("sync")}>
              <Icon name="sync" size={16} />
              {t("admin:services.syncNow")}
            </Button>
          )}
          <Button type="button" variant="ghost" onClick={() => action.mutate("disable")}>
            {t("admin:services.disable")}
          </Button>
        </>
      ) : null}
      <EditService service={service} connector={connector} />
      <Dialog
        title={t("admin:services.historyOf", { name: service.name })}
        closeLabel={t("admin:services.close")}
        trigger={
          <Button type="button" variant="ghost">
            <Icon name="clock" size={16} />
            {t("admin:services.history")}
          </Button>
        }
      >
        <SyncHistory service={service} />
      </Dialog>
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
    </>
  );
}

function ServiceTable({ services, onAdd }: { services: ServiceItem[]; onAdd: () => void }) {
  const t = useT();
  const format = useFormat();
  const connectors = useConnectors();
  const names = new Map((connectors.data ?? []).map((c) => [c.key, c.name]));
  const byKey = new Map((connectors.data ?? []).map((c) => [c.key, c]));
  const enabled = services.filter((s) => s.state === "enabled").length;
  const troubled = services.filter((s) => ["error", "unavailable"].includes(s.state)).length;
  if (services.length === 0) {
    return (
      <AdminSection title={t("admin:services.list")} icon="server">
        <AdminEmpty
          icon="server"
          title={t("admin:services.empty.title")}
          message={t("admin:services.empty.message")}
          action={
            <Button onClick={onAdd}>
              <Icon name="plus" size={16} />
              {t("admin:services.add")}
            </Button>
          }
        />
      </AdminSection>
    );
  }
  return (
    <>
      <AdminStats
        label={t("admin:services.list")}
        stats={[
          {
            key: "total",
            label: t("admin:services.stat.total"),
            value: format.number(services.length),
            icon: "server",
            tone: "info",
          },
          {
            key: "enabled",
            label: t("admin:services.stat.enabled"),
            value: format.number(enabled),
            icon: "check",
            tone: "ok",
          },
          {
            key: "troubled",
            label: t("admin:services.stat.troubled"),
            value: format.number(troubled),
            icon: "alert",
            tone: troubled ? "bad" : "neutral",
          },
        ]}
      />
      <AdminSection title={t("admin:services.list")} icon="server" flush>
        <AdminTable<ServiceItem>
          label={t("admin:services.list")}
          rows={services}
          rowKey={(s) => s.id}
          columns={[
            {
              key: "name",
              header: t("admin:services.name"),
              primary: true,
              render: (s) => (
                <span className="services-admin__name">
                  <strong>{s.name}</strong>
                  <span className="admin-muted">{names.get(s.connector) ?? s.connector}</span>
                  {s.public_url ? (
                    <a
                      className="services-admin__public"
                      href={s.public_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <Icon name="link" size={12} />
                      {s.public_url.replace(/^https?:\/\//, "").replace(/\/$/, "")}
                    </a>
                  ) : null}
                </span>
              ),
            },
            {
              key: "state",
              header: t("admin:services.stateColumn"),
              render: (s) => (
                <StatusBadge tone={STATE_TONE[s.display_state] ?? "neutral"}>
                  {t(`admin:services.state.${s.display_state}`)}
                </StatusBadge>
              ),
            },
            {
              key: "sync",
              header: t("admin:services.lastSync"),
              render: (s) => {
                if (s.sync.status === "running") {
                  const p = s.sync.progress;
                  return (
                    <LiveProgress
                      label={t("admin:services.syncing")}
                      done={p?.done}
                      total={p?.total}
                      detail={
                        p
                          ? p.total
                            ? `${format.number(p.done)} / ${format.number(p.total)}`
                            : t("admin:services.syncedSoFar", { count: p.done })
                          : null
                      }
                    />
                  );
                }
                if (continuous(byKey.get(s.connector))) return t("admin:services.continuous");
                const last = s.sync.last_success_at;
                return last
                  ? t("admin:services.lastSuccess", {
                      when: format.relative((Date.parse(last) - Date.now()) / 1000),
                    })
                  : t("admin:services.never");
              },
            },
          ]}
          actions={(s) => <ServiceActions service={s} connector={byKey.get(s.connector)} />}
        />
      </AdminSection>
    </>
  );
}

export function ServicesAdmin() {
  const t = useT();
  const [params, setParams] = useSearchParams();
  const [open, setOpen] = useState(params.get("add") === "1");
  const wantsAdd = params.get("add") === "1";
  useEffect(() => {
    if (wantsAdd) setOpen(true); // reached from another page's "Add a service" (client navigation)
  }, [wantsAdd]);
  function toggle(next: boolean) {
    setOpen(next);
    if (!next && params.has("add")) {
      params.delete("add");
      setParams(params, { replace: true });
    }
  }
  return (
    <AdminPage
      icon="plug"
      title={t("admin:services.title")}
      description={t("admin:services.subtitle")}
      secondary={
        <Link className="ds-button ds-button--ghost" to="/services">
          {t("admin:services.status")}
        </Link>
      }
      primary={
        <Dialog
          open={open}
          onOpenChange={toggle}
          size="lg"
          title={t("admin:services.wizard.title")}
          closeLabel={t("admin:services.close")}
          trigger={
            <Button type="button">
              <Icon name="plus" size={18} />
              {t("admin:services.add")}
            </Button>
          }
        >
          <AddServiceWizard />
        </Dialog>
      }
    >
      <DataRegion<ServiceItem[]>
        label={t("admin:services.list")}
        queryKey={SERVICES_KEY}
        queryFn={async () => (await unwrap<{ items: ServiceItem[] }>(api.GET("/api/v1/services"))).items}
        poll={pollServices}
      >
        {(services) => <ServiceTable services={services} onAdd={() => toggle(true)} />}
      </DataRegion>
    </AdminPage>
  );
}
