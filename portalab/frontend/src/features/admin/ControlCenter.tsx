import type { ReactNode } from "react";
import { Link } from "react-router";
import { api } from "../../api/client";
import { StatFigure } from "../../design-system/components/Collections";
import { Card } from "../../design-system/components/Content";
import { Icon } from "../../design-system/components/Icon";
import { PageHeader } from "../../design-system/components/PageHeader";
import { useFormat } from "../../i18n/format/useFormat";
import { type Translate, useT } from "../../i18n/hooks/useT";
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

interface Problem {
  id: string;
  title: string;
  kind: string;
  impact: number;
  criticality: number;
  since: string;
}

/**
 * Control Center (spec 020 US1, 027 T094): the portal status first, then what needs the administrator
 * (ranked, with a severity in text), one readable card per panel (known panels get a tailored body, others a
 * labelled list) and shortcuts to every administration area. Each panel keeps its own state — one failing
 * panel never hides the rest.
 */
const PANEL_ICONS: Record<string, string> = {
  configuration: "settings",
  services: "server",
  storage: "chart",
  observability: "activity",
  audit: "shield",
  support: "lifebuoy",
};

const SHORTCUTS: [string, string, string][] = [
  ["services", "/admin/services", "server"],
  ["configuration", "/admin/configuration", "settings"],
  ["roles", "/admin/roles", "key"],
  ["observability", "/admin/observability", "activity"],
  ["events", "/admin/events", "zap"],
  ["audit", "/admin/audit", "shield"],
  ["marketplace", "/admin/marketplace", "shop"],
  ["gamification", "/admin/gamification", "trophy"],
  ["news", "/admin/news", "newspaper"],
  ["support", "/admin/support", "lifebuoy"],
  ["moderation", "/admin/community/moderation", "users"],
  ["plugins", "/admin/plugins", "plug"],
  ["modules", "/admin/modules", "dashboard"],
  ["privacy", "/admin/privacy", "lock"],
];

const MAX_ATTENTION = 6;

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
      label={t("admin:cc.title")}
      queryKey={["admin", "overview"]}
      queryFn={async () => (await api.GET("/api/v1/admin/overview")).data as unknown as Overview}
    >
      {(overview) => <ControlCenterView overview={overview} />}
    </DataRegion>
  );
}

function ControlCenterView({ overview }: { overview: Overview }) {
  const t = useT();
  const health = overview.panels.find((p) => p.panel === "observability");
  const panels = overview.panels.filter((p) => p.panel !== "observability");
  const actions = overview.required_actions;
  return (
    <div className="control-center">
      <PageHeader level={2} icon="gauge" title={t("admin:cc.title")} context={t("admin:cc.subtitle")} />
      <StatusBanner health={health} />
      <section className="control-center__attention" aria-labelledby="cc-attention">
        <h3 id="cc-attention">
          <Icon name="bell" size={18} />
          {t("admin:cc.attention")}
          {actions.length ? <span className="ds-badge">{actions.length}</span> : null}
        </h3>
        {actions.length === 0 ? (
          <p className="control-center__calm">
            <Icon name="check" size={18} />
            {t("admin:cc.attention.none")}
          </p>
        ) : (
          <AttentionList actions={actions} />
        )}
      </section>
      <ul className="control-center__panels">
        {health ? (
          <li>
            <HealthCard panel={health} />
          </li>
        ) : null}
        {panels.map((panel) => (
          <li key={panel.panel}>
            <PanelCard panel={panel} />
          </li>
        ))}
      </ul>
      <section aria-labelledby="cc-shortcuts">
        <h3 id="cc-shortcuts" className="control-center__section-title">
          {t("admin:cc.shortcuts")}
        </h3>
        <ul className="control-center__shortcuts">
          {SHORTCUTS.map(([key, to, icon]) => (
            <li key={key}>
              <Link to={to}>
                <Icon name={icon} size={20} />
                {t(`admin:cc.shortcut.${key}`)}
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function StatusBanner({ health }: { health: PanelView | undefined }) {
  const t = useT();
  const format = useFormat();
  const status = health?.state === "available" ? String(health.data.status ?? "unknown") : "unknown";
  const known = ["ok", "degraded", "failing"].includes(status) ? status : "unknown";
  const since = secondsSince(health?.data.since);
  const icon = known === "ok" ? "check" : known === "unknown" ? "half" : "alert";
  return (
    <div className="control-center__status" data-status={known} role="status">
      <span className="control-center__status-icon" aria-hidden="true">
        <Icon name={icon} size={26} />
      </span>
      <span>
        <strong>{t(`admin:cc.status.${known}`)}</strong>
        {since !== null ? (
          <span className="control-center__muted">
            {t("admin:cc.status.since", { when: format.relative(since) })}
          </span>
        ) : null}
      </span>
    </div>
  );
}

function AttentionList({ actions }: { actions: RequiredAction[] }) {
  const t = useT();
  const format = useFormat();
  const shown = actions.slice(0, MAX_ATTENTION);
  return (
    <>
      <ol className="control-center__actions">
        {shown.map((action) => {
          const level = severity(action.impact, action.criticality);
          const since = secondsSince(action.since);
          return (
            <li key={action.id} data-severity={level}>
              <span className="control-center__severity">{t(`admin:cc.severity.${level}`)}</span>
              <span className="control-center__action-text">
                <Link to={action.link}>{titleOf(t, action.title_key)}</Link>
                {since !== null ? (
                  <span className="control-center__muted">{format.relative(since)}</span>
                ) : null}
              </span>
              <Icon name="chevron-right" size={18} />
            </li>
          );
        })}
      </ol>
      {actions.length > MAX_ATTENTION ? (
        <Link className="control-center__more" to="/admin/observability">
          {t("admin:cc.attention.more", { count: actions.length - MAX_ATTENTION })}
        </Link>
      ) : null}
    </>
  );
}

function StateChip({ state }: { state: string }) {
  const t = useT();
  return (
    <span className="ds-badge control-center__state" data-state={state}>
      {t(`admin:cc.state.${state}`)}
    </span>
  );
}

function panelTitle(t: Translate, name: string): string {
  const key = `admin:cc.panel.${name}`;
  const label = t(key);
  return label === `cc.panel.${name}` ? humanize(name) : label;
}

function humanize(key: string): string {
  const text = key.replace(/[_.-]+/g, " ").trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function PanelShell({
  panel,
  children,
  footer,
}: {
  panel: PanelView;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const t = useT();
  return (
    <Card
      className="control-center__panel"
      data-state={panel.state}
      title={panelTitle(t, panel.panel)}
      icon={PANEL_ICONS[panel.panel] ?? "dashboard"}
      actions={<StateChip state={panel.state} />}
    >
      {panel.state === "unavailable" ? (
        <p className="control-center__muted">{t("admin:cc.unavailable")}</p>
      ) : (
        children
      )}
      {footer ? <div className="control-center__panel-footer">{footer}</div> : null}
    </Card>
  );
}

function PanelCard({ panel }: { panel: PanelView }) {
  switch (panel.panel) {
    case "configuration":
      return <ConfigurationCard panel={panel} />;
    case "services":
      return <ServicesCard panel={panel} />;
    case "storage":
      return <StorageCard panel={panel} />;
    case "audit":
      return <AuditCard panel={panel} />;
    default:
      return <GenericCard panel={panel} />;
  }
}

function ConfigurationCard({ panel }: { panel: PanelView }) {
  const t = useT();
  const format = useFormat();
  const done = panel.data.first_run_completed !== false;
  return (
    <PanelShell
      panel={panel}
      footer={<Link to="/admin/configuration">{t("admin:cc.configuration.manage")}</Link>}
    >
      <div className="control-center__figures">
        <StatFigure
          label={t("admin:cc.configuration.setup")}
          value={t(done ? "admin:cc.configuration.setupDone" : "admin:cc.configuration.setupPending")}
        />
        <StatFigure
          label={t("admin:cc.configuration.policies")}
          value={format.number(Number(panel.data.active_policies ?? 0))}
        />
        <StatFigure
          label={t("admin:cc.configuration.invalid")}
          value={format.number(Number(panel.data.invalid_stored_values ?? 0))}
        />
      </div>
    </PanelShell>
  );
}

function ServicesCard({ panel }: { panel: PanelView }) {
  const t = useT();
  const format = useFormat();
  const total = Number(panel.data.total ?? 0);
  const byState = (panel.data.by_state ?? {}) as Record<string, number>;
  return (
    <PanelShell
      panel={panel}
      footer={
        <>
          <Link to="/admin/services?add=1" className="control-center__primary-link">
            <Icon name="plus" size={16} />
            {t("admin:cc.services.add")}
          </Link>
          <Link to="/admin/services">{t("admin:cc.services.manage")}</Link>
        </>
      }
    >
      {total === 0 ? (
        <p className="control-center__muted">{t("admin:cc.services.empty")}</p>
      ) : (
        <>
          <div className="control-center__figures">
            <StatFigure label={t("admin:cc.services.total")} value={format.number(total)} />
            <StatFigure
              label={t("admin:cc.services.troubled")}
              value={format.number(Number(panel.data.troubled ?? 0))}
            />
          </div>
          <ul className="control-center__chips">
            {Object.entries(byState).map(([state, count]) => (
              <li key={state} className="ds-badge" data-service-state={state}>
                {t(`admin:cc.services.state.${state}`)} · {format.number(count)}
              </li>
            ))}
          </ul>
        </>
      )}
    </PanelShell>
  );
}

function StorageCard({ panel }: { panel: PanelView }) {
  const t = useT();
  const total = Number(panel.data.database_bytes ?? 0);
  const largest = (panel.data.largest ?? []) as { schema: string; bytes: number }[];
  const top = Math.max(1, ...largest.map((entry) => entry.bytes));
  return (
    <PanelShell panel={panel}>
      <StatFigure label={t("admin:cc.storage.database")} value={formatBytes(total)} />
      {largest.length ? (
        <>
          <p className="control-center__label">{t("admin:cc.storage.largest")}</p>
          <ul className="control-center__bars">
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
        </>
      ) : null}
    </PanelShell>
  );
}

function AuditCard({ panel }: { panel: PanelView }) {
  const t = useT();
  const format = useFormat();
  const since = secondsSince(panel.data.last_checkpoint_at);
  return (
    <PanelShell panel={panel} footer={<Link to="/admin/audit">{t("admin:cc.audit.manage")}</Link>}>
      <div className="control-center__figures">
        <StatFigure
          label={t("admin:cc.audit.checkpoint")}
          value={
            <span className="control-center__small-value">
              {since !== null ? format.relative(since) : "—"}
            </span>
          }
        />
        <StatFigure
          label={t("admin:cc.audit.unsealed")}
          value={format.number(Number(panel.data.unsealed_entries ?? 0))}
        />
      </div>
    </PanelShell>
  );
}

function HealthCard({ panel }: { panel: PanelView }) {
  const t = useT();
  const problems = (panel.data.problems ?? []) as Problem[];
  return (
    <PanelShell
      panel={panel}
      footer={<Link to="/admin/observability">{t("admin:cc.observability.manage")}</Link>}
    >
      {problems.length === 0 ? (
        <p className="control-center__muted">{t("admin:cc.observability.none")}</p>
      ) : (
        <>
          <p className="control-center__label">{t("admin:cc.observability.problems")}</p>
          <ul className="control-center__problems">
            {problems.map((problem) => {
              const level = severity(problem.impact, problem.criticality);
              return (
                <li key={`${problem.kind}:${problem.id}`} data-severity={level}>
                  <span className="control-center__severity">{t(`admin:cc.severity.${level}`)}</span>
                  {problem.title}
                </li>
              );
            })}
          </ul>
        </>
      )}
    </PanelShell>
  );
}

function GenericCard({ panel }: { panel: PanelView }) {
  const entries = Object.entries(panel.data).filter(
    ([, value]) => typeof value !== "object" || value === null,
  );
  return (
    <PanelShell panel={panel}>
      <dl className="control-center__facts">
        {entries.map(([key, value]) => (
          <div key={key}>
            <dt>{humanize(key)}</dt>
            <dd>{value === null ? "—" : String(value)}</dd>
          </div>
        ))}
      </dl>
    </PanelShell>
  );
}
