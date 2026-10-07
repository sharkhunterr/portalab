import { useQuery } from "@tanstack/react-query";
import { type ReactNode, useId } from "react";
import { Link } from "react-router";
import { api } from "../../api/client";
import { Icon } from "../../design-system/components/Icon";
import { Dialog } from "../../design-system/components/Overlays";
import { PageHeader } from "../../design-system/components/PageHeader";
import { FunctionalState } from "../../design-system/FunctionalState";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { DataRegion } from "../../state/regions";
import { useIncidents } from "../support/incidents/api";
import { SeverityBadge } from "../support/incidents/IncidentParts";
import { useMaintenances } from "../support/incidents/maintenance";
import "./services.css";

/**
 * Services overview and detail page (spec 006 T024). Each detail section is independent and shows its own
 * state (available, no data, unavailable); the server decides which sections a user may see (permission
 * tiers). Health states carry an icon and a text label, never color alone. Strings externalized for 026.
 */
export const servicesHealthStrings = {
  title: "Services",
  overview: "Service status",
  empty: "No service is monitored yet.",
  details: (name: string) => `Details of ${name}`,
  detailTitle: (name: string) => `${name} — health`,
  availability: (ratio: number | null) =>
    ratio === null ? "availability unknown" : `${(ratio * 100).toFixed(1)}% available (24 h)`,
  noData: "No data yet",
  sectionUnavailable: "This section is unavailable right now.",
  sections: {
    state: "Current state",
    availability: "Availability",
    maintenance: "Maintenance",
    incidents: "Incidents",
    sync: "Synchronization",
    history: "Recent changes",
    errors: "Recent errors",
    tickets: "Tickets",
    infrastructure: "Infrastructure",
    operations: "Operations",
  } as Record<string, string>,
  states: {
    operational: "Operational",
    degraded: "Degraded",
    unavailable: "Unavailable",
    maintenance: "Under maintenance",
    unknown: "Unknown",
  } as Record<string, string>,
  since: (at: string) => `since ${at}`,
  notAvailable: "not available",
  downtime: (seconds: number) => `${Math.round(seconds / 60)} min of downtime`,
  gaps: (hours: number) => `${hours} h without monitoring`,
  window: (title: string, starts: string, ends: string) => `${title}: ${starts} → ${ends}`,
  syncStatus: (status: string, at: string | null) => `${status}${at ? ` · last success ${at}` : ""}`,
  transition: (from: string | null, to: string, at: string) => `${from ?? "—"} → ${to} (${at})`,
  error: (code: string, count: number, message: string) => `${code} ×${count}: ${message}`,
} as const;

type HealthState = "operational" | "degraded" | "unavailable" | "maintenance" | "unknown";

interface OverviewItem {
  id: string;
  name: string;
  connector: string;
  state: HealthState;
  availability: number | null;
  link?: string | null;
}

interface Section {
  state: "available" | "no-data" | "unavailable";
  as_of: string;
  detail?: string;
  data?: unknown;
}

interface Detail {
  service: { id: string; name: string | null };
  sections: Record<string, Section>;
}

const ICONS: Record<HealthState, string> = {
  operational: "M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z",
  degraded: "M12 2a10 10 0 1 0 0 20V2z",
  unavailable: "M4 4l16 16M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z",
  maintenance: "M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.1-2.1z",
  unknown: "M9 9a3 3 0 1 1 3 3v2m0 3v.01",
};

export function HealthBadge({ state }: { state: HealthState }) {
  return (
    <span className={`health-badge health-badge--${state}`} data-state={state}>
      <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false">
        <path d={ICONS[state] ?? ICONS.unknown} fill="none" stroke="currentColor" strokeWidth="2" />
      </svg>{" "}
      {servicesHealthStrings.states[state] ?? state}
    </span>
  );
}

interface ListItem {
  id?: string;
  key?: string;
  title?: string;
  label?: string;
}

function SectionBody({ name, data }: { name: string; data: unknown }): ReactNode {
  const s = servicesHealthStrings;
  const value = data as Record<string, unknown> & unknown[];
  switch (name) {
    case "state":
      return (
        <p>
          <HealthBadge state={value.state as HealthState} /> {s.since(String(value.since))}
        </p>
      );
    case "availability":
      return (
        <p>
          {s.availability((value.availability as number | null) ?? null)}
          {typeof value.downtime_seconds === "number" ? ` · ${s.downtime(value.downtime_seconds)}` : ""}
          {typeof value.gap_hours === "number" && value.gap_hours > 0 ? ` · ${s.gaps(value.gap_hours)}` : ""}
        </p>
      );
    case "maintenance":
      return (
        <ul>
          {(value as unknown as Array<{ id: string; title: string; starts_at: string; ends_at: string }>).map(
            (w) => (
              <li key={w.id}>{s.window(w.title, w.starts_at, w.ends_at)}</li>
            ),
          )}
        </ul>
      );
    case "sync":
      return <p>{s.syncStatus(String(value.status), (value.last_success_at as string | null) ?? null)}</p>;
    case "history":
      return (
        <ul>
          {(value.transitions as Array<{ from: string | null; to: string; occurred_at: string }>).map((t) => (
            <li key={`${t.occurred_at}-${t.to}`}>{s.transition(t.from, t.to, t.occurred_at)}</li>
          ))}
        </ul>
      );
    case "errors":
      return (
        <ul>
          {(value as unknown as Array<{ code: string; count: number; message: string }>).map((e) => (
            <li key={e.code}>{s.error(e.code, e.count, e.message)}</li>
          ))}
        </ul>
      );
    case "incidents":
      // incidents live in Support (016): link to their page
      return (
        <ul>
          {(value as unknown as Array<{ id: string; title: string; status: string }>).map((i) => (
            <li key={i.id}>
              <Link to={`/incidents/${i.id}`}>{i.title}</Link> ({i.status})
            </li>
          ))}
        </ul>
      );
    case "infrastructure": {
      const metrics = value.metrics as Record<string, { available: boolean; value?: number; unit?: string }>;
      return (
        <dl>
          {Object.entries(metrics).map(([metric, item]) => (
            <div key={metric}>
              <dt>{metric}</dt>
              <dd>{item.available ? `${item.value} ${item.unit ?? ""}` : s.notAvailable}</dd>
            </div>
          ))}
        </dl>
      );
    }
    default:
      return (
        <ul>
          {((Array.isArray(data) ? data : []) as ListItem[]).map((item) => (
            <li key={item.id ?? item.key}>{item.title ?? item.label}</li>
          ))}
        </ul>
      );
  }
}

function SectionView({ name, section }: { name: string; section: Section }) {
  const headingId = useId();
  const title = servicesHealthStrings.sections[name] ?? name;
  return (
    <section aria-labelledby={headingId} data-section={name}>
      <h4 id={headingId}>{title}</h4>
      {section.state === "unavailable" ? (
        <FunctionalState
          state="unavailable"
          detail={section.detail ?? servicesHealthStrings.sectionUnavailable}
        />
      ) : section.state === "no-data" ? (
        <p>{servicesHealthStrings.noData}</p>
      ) : (
        <SectionBody name={name} data={section.data} />
      )}
    </section>
  );
}

export function ServiceDetail({ serviceId, name }: { serviceId: string; name: string }) {
  const headingId = useId();
  const query = useQuery({
    queryKey: ["services", serviceId, "health"],
    queryFn: async () =>
      (await api.GET("/api/v1/services/{service_id}/health", { params: { path: { service_id: serviceId } } }))
        .data as unknown as Detail,
  });
  return (
    <article aria-labelledby={headingId}>
      <h3 id={headingId}>{servicesHealthStrings.detailTitle(name)}</h3>
      {query.isPending ? <FunctionalState state="loading" /> : null}
      {query.isError ? <FunctionalState state="error" onRetry={() => void query.refetch()} /> : null}
      {query.data
        ? Object.entries(query.data.sections).map(([section, value]) => (
            <SectionView key={section} name={section} section={value} />
          ))
        : null}
    </article>
  );
}

/** 027: a recognisable icon per kind of service. */
const CONNECTOR_ICONS: Record<string, string> = {
  plex: "play",
  jellyfin: "play",
  emby: "play",
  radarr: "film",
  sonarr: "tv",
  seerr: "inbox",
  tautulli: "chart",
  tmdb: "database",
  grimmory: "book",
  romm: "joystick",
  qbittorrent: "package",
  deluge: "package",
};

const RANK: Record<HealthState, number> = {
  unavailable: 0,
  degraded: 1,
  maintenance: 2,
  unknown: 3,
  operational: 4,
};

/**
 * Services as members see them (027, under Support): how everything goes at a glance, what is wrong now
 * (incidents) or planned (maintenance), then one card per service — its state, how available it was over
 * the day, a way to open it when it has a public address, and its details on demand. Nothing to configure
 * here: services are added and managed in the administration.
 */
export function ServicesHealth() {
  const t = useT();
  const format = useFormat();
  const incidents = useIncidents("open");
  const maintenances = useMaintenances();
  const open = Array.isArray(incidents.data) ? incidents.data : [];
  const planned = Array.isArray(maintenances.data) ? maintenances.data : [];
  return (
    <div className="account-page services-page">
      <PageHeader
        level={2}
        icon="server"
        title={t("support:status.title")}
        context={t("support:status.subtitle")}
      />
      <DataRegion<OverviewItem[]>
        label={servicesHealthStrings.overview}
        queryKey={["services", "health"]}
        queryFn={async () =>
          ((await api.GET("/api/v1/services/health")).data as unknown as { items: OverviewItem[] }).items
        }
      >
        {(items) => {
          const troubled = items.filter((i) => i.state === "unavailable" || i.state === "degraded").length;
          const maintenance = items.filter((i) => i.state === "maintenance").length;
          const tone = troubled || open.length ? "bad" : maintenance ? "warn" : "ok";
          const sorted = [...items].sort(
            (a, b) => (RANK[a.state] ?? 3) - (RANK[b.state] ?? 3) || a.name.localeCompare(b.name),
          );
          return (
            <>
              <section className="services-status ds-card" data-tone={tone} aria-live="polite">
                <span className="services-status__icon" aria-hidden="true">
                  <Icon name={tone === "ok" ? "check" : tone === "warn" ? "wrench" : "alert"} size={28} />
                </span>
                <span className="services-status__text">
                  <strong>
                    {items.length === 0
                      ? servicesHealthStrings.empty
                      : troubled
                        ? t("support:status.troubled", { count: troubled })
                        : open.length
                          ? t("support:status.incidents", { count: open.length })
                          : maintenance
                            ? t("support:status.maintenance", { count: maintenance })
                            : t("support:status.allGood")}
                  </strong>
                  <span>{t("support:status.count", { count: items.length })}</span>
                </span>
              </section>
              {open.length ? (
                <section className="services-block" aria-labelledby="services-incidents">
                  <h3 id="services-incidents">
                    <Icon name="alert" size={18} /> {t("support:status.openIncidents")}
                  </h3>
                  <ul className="services-incidents">
                    {open.map((incident) => (
                      <li key={incident.id} data-severity={incident.severity}>
                        <Link to={`/incidents/${incident.id}`} className="services-incidents__item">
                          <SeverityBadge severity={incident.severity} />
                          <strong>{incident.title}</strong>
                          <span className="services-page__meta">
                            {t(`support:state.${incident.state}`)} ·{" "}
                            {format.relative((Date.parse(incident.created_at) - Date.now()) / 1000)}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
              {planned.length ? (
                <section className="services-block" aria-labelledby="services-maintenance">
                  <h3 id="services-maintenance">
                    <Icon name="wrench" size={18} /> {t("support:status.plannedMaintenance")}
                  </h3>
                  <ul className="services-maintenance">
                    {planned.map((window) => (
                      <li key={window.id}>
                        <strong>{window.title}</strong>
                        <span className="services-page__meta">
                          {format.dateTime(window.starts_at)} → {format.dateTime(window.ends_at)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
              {items.length ? (
                <ul aria-label={servicesHealthStrings.overview} className="services-page__grid">
                  {sorted.map((item) => (
                    <ServiceCard key={item.id} item={item} />
                  ))}
                </ul>
              ) : null}
            </>
          );
        }}
      </DataRegion>
      <p className="services-page__meta">
        <Link to="/incidents">{t("support:status.history")}</Link>
      </p>
    </div>
  );
}

function ServiceCard({ item }: { item: OverviewItem }) {
  const t = useT();
  const ratio = item.availability;
  return (
    <li className="ds-card services-page__card" data-state={item.state}>
      <span className="services-page__name">
        <span className="services-page__icon" aria-hidden="true">
          <Icon name={CONNECTOR_ICONS[item.connector] ?? "server"} size={20} />
        </span>
        <strong>{item.name}</strong>
      </span>
      <HealthBadge state={item.state} />
      <span className="services-page__uptime">
        <span className="services-page__bar" aria-hidden="true">
          <span style={{ inlineSize: `${Math.round((ratio ?? 0) * 100)}%` }} />
        </span>
        <span className="services-page__meta">{servicesHealthStrings.availability(ratio)}</span>
      </span>
      <span className="services-page__actions">
        {item.link ? (
          <a className="ds-button ds-button--primary" href={item.link} target="_blank" rel="noreferrer">
            <Icon name="link" size={16} />
            {t("support:status.open")}
          </a>
        ) : null}
        <Dialog
          title={item.name}
          closeLabel={t("support:status.close")}
          size="lg"
          trigger={
            <button
              type="button"
              className="ds-button ds-button--secondary"
              aria-label={servicesHealthStrings.details(item.name)}
            >
              <Icon name="info" size={16} />
              {t("support:status.details")}
            </button>
          }
        >
          <ServiceDetail serviceId={item.id} name={item.name} />
        </Dialog>
      </span>
    </li>
  );
}
