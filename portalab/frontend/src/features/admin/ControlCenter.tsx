import type { ReactNode } from "react";
import { Link } from "react-router";
import { api } from "../../api/client";
import {
  AdminGrid,
  AdminPage,
  AdminSection,
  AdminStats,
  KeyValues,
  type Stat,
  StatusBadge,
  type Tone,
} from "../../design-system/admin/AdminKit";
import { CountBadge } from "../../design-system/components/CountBadge";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { type Translate, useT } from "../../i18n/hooks/useT";
import { useAttention } from "../../shell/nav/attention";
import { useNavigationView } from "../../shell/nav/NavigationProvider";
import { useShellStrings } from "../../shell/strings";
import { DataRegion } from "../../state/regions";
import "./admin.css";

type Data = Record<string, unknown>;

interface PanelView {
  panel: string;
  state: string;
  data: Data;
}

interface RequiredAction {
  id: string;
  title_key: string;
  link: string;
  impact?: number;
  criticality?: number;
  since?: string;
}

interface Overview {
  panels: PanelView[];
  required_actions: RequiredAction[];
}

/**
 * Control Center (spec 020 US1, 027 T094) on the administration kit: key figures first (health, what needs
 * you, services, storage, audit), then what needs the administrator as a ranked list with a severity in
 * text, one section per panel and the shortcuts to every administration area. Each panel keeps its own
 * state — one failing panel never hides the rest.
 */
const PANEL_ICONS: Record<string, string> = {
  configuration: "settings",
  services: "server",
  storage: "chart",
  observability: "activity",
  audit: "shield",
  support: "lifebuoy",
};

const MAX_ATTENTION = 8;
const STATE_TONE: Record<string, Tone> = {
  available: "ok",
  partial: "warn",
  stale: "warn",
  unavailable: "bad",
  "no-data": "neutral",
};
const STATUS_TONE: Record<string, Tone> = { ok: "ok", degraded: "warn", failing: "bad", unknown: "neutral" };
const SEVERITY_TONE: Record<string, Tone> = { high: "bad", medium: "warn", low: "neutral" };

export function severity(impact = 0, criticality = 0): "high" | "medium" | "low" {
  const score = Math.max(impact, criticality);
  return score >= 4 ? "high" : score >= 3 ? "medium" : "low";
}

/** Required-action titles are catalog keys, except problems reported as plain text by Observability. */
function titleOf(t: Translate, key: string): string {
  return /^[a-z][a-z0-9_-]*:[A-Za-z0-9_.-]+$/.test(key) ? t(key) : key;
}

export function formatBytes(bytes: number, locale?: string): string {
  const units = ["B", "kB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const digits = value < 10 && unit > 0 ? 1 : 0;
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: digits }).format(value)} ${units[unit]}`;
}

function secondsSince(iso: unknown): number | null {
  if (typeof iso !== "string") return null;
  const time = Date.parse(iso);
  return Number.isNaN(time) ? null : (time - Date.now()) / 1000;
}

export function ControlCenter() {
  const t = useT();
  return (
    <DataRegion<Overview>
      label={t("admin:cc.overview")}
      queryKey={["admin", "overview"]}
      queryFn={async () => (await api.GET("/api/v1/admin/overview")).data as unknown as Overview}
    >
      {(overview) => <ControlCenterView overview={overview} />}
    </DataRegion>
  );
}

function ControlCenterView({ overview }: { overview: Overview }) {
  const t = useT();
  const strings = useShellStrings();
  const { view } = useNavigationView();
  const hubs = view.sections.filter((s) => s.audience === "administration").flatMap((s) => s.topics);
  // #98: what members and the portal wait for — one line per page with its count, the busiest first
  const attention = useAttention();
  const waiting = view.sections
    .flatMap((section) => [...section.entries, ...section.topics.flatMap((topic) => topic.entries)])
    .filter(
      (entry, index, all) => attention.of(entry) > 0 && all.findIndex((e) => e.key === entry.key) === index,
    )
    .sort((a, b) => attention.of(b) - attention.of(a));
  const format = useFormat();
  const panel = (name: string) => overview.panels.find((p) => p.panel === name);
  const health = panel("observability");
  const status = health?.state === "available" ? String(health.data.status ?? "unknown") : "unknown";
  const known = status in STATUS_TONE ? status : "unknown";
  const actions = overview.required_actions;
  const high = actions.filter((a) => severity(a.impact, a.criticality) === "high").length;
  const services = panel("services");
  const storage = panel("storage");
  const audit = panel("audit");
  const stats: Stat[] = [
    {
      key: "health",
      label: t("admin:cc.panel.observability"),
      value: t(`admin:cc.status.${known}`),
      tone: STATUS_TONE[known],
      icon: "activity",
      to: "/admin/observability",
    },
    {
      key: "attention",
      label: t("admin:cc.attention"),
      value: format.number(actions.length),
      hint: high ? t("admin:cc.highCount", { count: high }) : undefined,
      tone: high ? "bad" : actions.length ? "warn" : "ok",
      icon: "bell",
    },
  ];
  if (services?.state === "available" || services?.state === "partial") {
    const troubled = Number(services.data.troubled ?? 0);
    stats.push({
      key: "services",
      label: t("admin:cc.panel.services"),
      value: format.number(Number(services.data.total ?? 0)),
      hint: troubled ? t("admin:cc.services.troubledCount", { count: troubled }) : undefined,
      tone: troubled ? "warn" : Number(services.data.total ?? 0) ? "ok" : "neutral",
      icon: "server",
      to: "/admin/services",
    });
  }
  if (storage?.state === "available") {
    stats.push({
      key: "storage",
      label: t("admin:cc.panel.storage"),
      value: formatBytes(Number(storage.data.database_bytes ?? 0)),
      icon: "chart",
      tone: "info",
    });
  }
  if (audit?.state === "available") {
    const since = secondsSince(audit.data.last_checkpoint_at);
    stats.push({
      key: "audit",
      label: t("admin:cc.panel.audit"),
      value: format.number(Number(audit.data.unsealed_entries ?? 0)),
      hint: since !== null ? t("admin:cc.audit.sealed", { when: format.relative(since) }) : undefined,
      icon: "shield",
      tone: "info",
      to: "/admin/audit",
    });
  }
  const others = overview.panels.filter((p) => p.panel !== "observability");
  return (
    <AdminPage
      icon="gauge"
      title={t("admin:cc.title")}
      description={t("admin:cc.subtitle")}
      secondary={
        <StatusBadge tone={STATUS_TONE[known] ?? "neutral"}>{t(`admin:cc.status.${known}`)}</StatusBadge>
      }
    >
      <AdminStats stats={stats} label={t("admin:cc.figures")} />
      <AdminGrid>
        <AdminSection
          title={t("admin:cc.attention")}
          icon="bell"
          flush
          actions={
            actions.length > MAX_ATTENTION ? (
              <Link to="/admin/observability" className="ds-button ds-button--ghost">
                {t("admin:cc.attention.more", { count: actions.length - MAX_ATTENTION })}
              </Link>
            ) : undefined
          }
        >
          {actions.length === 0 ? (
            <p className="control-center__calm">
              <Icon name="check" size={18} />
              {t("admin:cc.attention.none")}
            </p>
          ) : (
            <ol className="admin-list control-center__actions">
              {actions.slice(0, MAX_ATTENTION).map((action) => {
                const level = severity(action.impact, action.criticality);
                const since = secondsSince(action.since);
                return (
                  <li key={action.id}>
                    <StatusBadge tone={SEVERITY_TONE[level] ?? "neutral"}>
                      {t(`admin:cc.severity.${level}`)}
                    </StatusBadge>
                    <span className="admin-list__main">
                      <Link to={action.link}>{titleOf(t, action.title_key)}</Link>
                      {since !== null ? <span className="admin-muted">{format.relative(since)}</span> : null}
                    </span>
                  </li>
                );
              })}
            </ol>
          )}
        </AdminSection>
        <AdminSection title={t("admin:cc.waiting")} icon="inbox" flush>
          {waiting.length === 0 ? (
            <p className="control-center__calm">
              <Icon name="check" size={18} />
              {t("admin:cc.waiting.none")}
            </p>
          ) : (
            <ul className="admin-list control-center__waiting">
              {waiting.map((entry) => (
                <li key={entry.key}>
                  <Link to={entry.route ?? "/admin"} className="control-center__waiting-link">
                    <Icon name={entry.icon ?? "inbox"} size={18} />
                    <span className="admin-list__main">{strings.label(entry.label_key)}</span>
                    <CountBadge
                      count={attention.of(entry)}
                      label={t("shell:attention", { count: attention.of(entry) })}
                    />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </AdminSection>
        {others.map((p) => (
          <PanelSection key={p.panel} panel={p} />
        ))}
        <AdminSection title={t("admin:cc.shortcuts")} icon="compass" span="full">
          <ul className="control-center__hubs">
            {hubs.map((hub) => (
              <li key={hub.key}>
                <Link to={hub.route ?? hub.entries[0]?.route ?? "/admin"} className="control-center__hub">
                  <span className="connector-card__icon" aria-hidden="true">
                    <Icon name={hub.icon ?? "settings"} size={20} />
                  </span>
                  <span className="services-admin__name">
                    <strong className="control-center__hub-title">
                      {strings.label(hub.label_key)}
                      <CountBadge
                        count={attention.ofEntries(hub.entries)}
                        label={t("shell:attention", { count: attention.ofEntries(hub.entries) })}
                      />
                    </strong>
                    <span className="admin-muted">
                      {hub.entries.map((entry) => strings.label(entry.label_key)).join(" · ")}
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </AdminSection>
      </AdminGrid>
    </AdminPage>
  );
}

function panelTitle(t: Translate, name: string): string {
  const label = t(`admin:cc.panel.${name}`);
  return label === `cc.panel.${name}` ? humanize(name) : label;
}

function humanize(key: string): string {
  const text = key.replace(/[_.-]+/g, " ").trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function PanelSection({ panel }: { panel: PanelView }) {
  const t = useT();
  return (
    <AdminSection
      title={panelTitle(t, panel.panel)}
      icon={PANEL_ICONS[panel.panel] ?? "dashboard"}
      actions={
        <StatusBadge tone={STATE_TONE[panel.state] ?? "neutral"}>
          {t(`admin:cc.state.${panel.state}`)}
        </StatusBadge>
      }
    >
      {panel.state === "unavailable" ? (
        <p className="admin-muted">{t("admin:cc.unavailable")}</p>
      ) : (
        <PanelBody panel={panel} />
      )}
    </AdminSection>
  );
}

function PanelBody({ panel }: { panel: PanelView }) {
  const t = useT();
  const format = useFormat();
  const data = panel.data;
  switch (panel.panel) {
    case "configuration":
      return (
        <>
          <KeyValues
            items={[
              {
                key: "setup",
                label: t("admin:cc.configuration.setup"),
                value: t(
                  data.first_run_completed === false
                    ? "admin:cc.configuration.setupPending"
                    : "admin:cc.configuration.setupDone",
                ),
              },
              {
                key: "policies",
                label: t("admin:cc.configuration.policies"),
                value: format.number(Number(data.active_policies ?? 0)),
              },
              {
                key: "invalid",
                label: t("admin:cc.configuration.invalid"),
                value: format.number(Number(data.invalid_stored_values ?? 0)),
              },
            ]}
          />
          <PanelLinks>
            <Link to="/admin/configuration">{t("admin:cc.configuration.manage")}</Link>
          </PanelLinks>
        </>
      );
    case "services": {
      const total = Number(data.total ?? 0);
      const byState = (data.by_state ?? {}) as Record<string, number>;
      return (
        <>
          {total === 0 ? (
            <p className="admin-muted">{t("admin:cc.services.empty")}</p>
          ) : (
            <ul className="control-center__chips">
              {Object.entries(byState).map(([state, count]) => (
                <li key={state}>
                  <StatusBadge tone={state === "ok" ? "ok" : state === "unknown" ? "neutral" : "warn"}>
                    {t(`admin:cc.services.state.${state}`)} · {format.number(count)}
                  </StatusBadge>
                </li>
              ))}
            </ul>
          )}
          <PanelLinks>
            <Link to="/admin/services?add=1" className="ds-button ds-button--primary">
              <Icon name="plus" size={16} />
              {t("admin:cc.services.add")}
            </Link>
            <Link to="/admin/services">{t("admin:cc.services.manage")}</Link>
          </PanelLinks>
        </>
      );
    }
    case "storage": {
      const largest = (data.largest ?? []) as { schema: string; bytes: number }[];
      const top = Math.max(1, ...largest.map((entry) => entry.bytes));
      return (
        <>
          <KeyValues
            items={[
              {
                key: "size",
                label: t("admin:cc.storage.database"),
                value: formatBytes(Number(data.database_bytes ?? 0)),
              },
            ]}
          />
          {largest.length ? (
            <ul className="control-center__bars" aria-label={t("admin:cc.storage.largest")}>
              {largest.map((entry) => (
                <li key={entry.schema}>
                  <span>{entry.schema}</span>
                  <span className="control-center__bar" aria-hidden="true">
                    <span style={{ inlineSize: `${Math.round((entry.bytes / top) * 100)}%` }} />
                  </span>
                  <span>{formatBytes(entry.bytes)}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </>
      );
    }
    case "audit": {
      const since = secondsSince(data.last_checkpoint_at);
      return (
        <>
          <KeyValues
            items={[
              {
                key: "seal",
                label: t("admin:cc.audit.checkpoint"),
                value: since !== null ? format.relative(since) : "—",
              },
              {
                key: "unsealed",
                label: t("admin:cc.audit.unsealed"),
                value: format.number(Number(data.unsealed_entries ?? 0)),
              },
            ]}
          />
          <PanelLinks>
            <Link to="/admin/audit">{t("admin:cc.audit.manage")}</Link>
          </PanelLinks>
        </>
      );
    }
    default: {
      const entries = Object.entries(data).filter(([, value]) => typeof value !== "object" || value === null);
      return (
        <KeyValues
          items={entries.map(([key, value]) => ({
            key,
            label: humanize(key),
            value: value === null ? "—" : String(value),
          }))}
        />
      );
    }
  }
}

function PanelLinks({ children }: { children: ReactNode }) {
  return <div className="control-center__links">{children}</div>;
}
