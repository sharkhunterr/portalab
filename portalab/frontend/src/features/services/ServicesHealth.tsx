import { useQuery } from "@tanstack/react-query";
import { useId } from "react";
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
  /** 027: whether its trouble counts in the portal's health (its alerting rule). */
  degrades_portal?: boolean;
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

interface Transition {
  from: string | null;
  to: string;
  occurred_at: string;
}

const STATE_TONES: Record<string, string> = {
  operational: "ok",
  degraded: "warn",
  unavailable: "bad",
  maintenance: "info",
  unknown: "none",
};

/** What a section holds, or nothing when it is empty or did not load (a quiet line says which). */
function sectionData<T>(detail: Detail | undefined, name: string): T | null {
  const section = detail?.sections[name];
  if (!section || section.state !== "available") return null;
  return (section.data ?? null) as T | null;
}

/**
 * A service's health (spec 006 T024; 027 redesign): its state and since when, the day in figures
 * (availability, downtime, time without monitoring, last sync), the last 48 hours as micro-bars, the
 * outages as a timeline with their duration, then incidents, planned maintenance, recent errors and
 * tickets — each shown only when there is something to tell. The server still decides which sections a
 * viewer may see.
 */
export function ServiceDetail({ serviceId, name }: { serviceId: string; name: string }) {
  const t = useT();
  const format = useFormat();
  const headingId = useId();
  const query = useQuery({
    queryKey: ["services", serviceId, "health"],
    queryFn: async () =>
      (await api.GET("/api/v1/services/{service_id}/health", { params: { path: { service_id: serviceId } } }))
        .data as unknown as Detail,
  });
  const detail = query.data;
  const ago = (iso: string | null | undefined) =>
    iso ? format.relative((Date.parse(iso) - Date.now()) / 1000) : "—";
  const state = sectionData<{ state: HealthState; since: string }>(detail, "state");
  const availability = sectionData<{
    availability: number | null;
    downtime_seconds?: number;
    gap_hours?: number;
  }>(detail, "availability");
  const sync = sectionData<{ status: string; last_success_at: string | null }>(detail, "sync");
  const transitions = sectionData<{ transitions: Transition[] }>(detail, "history")?.transitions ?? [];
  const incidents =
    sectionData<Array<{ id: string; title: string; status: string }>>(detail, "incidents") ?? [];
  const maintenance =
    sectionData<Array<{ id: string; title: string; starts_at: string; ends_at: string }>>(
      detail,
      "maintenance",
    ) ?? [];
  const errors = sectionData<Array<{ code: string; count: number; message: string }>>(detail, "errors") ?? [];
  const tickets =
    sectionData<Array<{ id?: string; title?: string; label?: string }>>(detail, "tickets") ?? [];
  const unavailable = Object.entries(detail?.sections ?? {})
    // what a member cares about; infrastructure and operations stay quiet when they cannot answer
    .filter(
      ([key, section]) => section.state === "unavailable" && !["infrastructure", "operations"].includes(key),
    )
    .map(([key, section]) => ({ key, detail: section.detail }));
  // the periods between changes, newest first, with how long each lasted
  const periods = [...(Array.isArray(transitions) ? transitions : [])]
    .map((change, index, list) => {
      const end = list[index + 1]?.occurred_at ?? null;
      return {
        state: change.to,
        start: change.occurred_at,
        seconds: (Date.parse(end ?? new Date().toISOString()) - Date.parse(change.occurred_at)) / 1000,
        current: end === null,
      };
    })
    .reverse()
    .slice(0, 12);
  const duration = (seconds: number) =>
    seconds < 3600
      ? t("support:status.detail.minutes", { count: Math.max(1, Math.round(seconds / 60)) })
      : seconds < 172800
        ? t("support:status.detail.hours", { count: Math.round(seconds / 3600) })
        : t("support:status.detail.days", { count: Math.round(seconds / 86400) });
  return (
    <article aria-labelledby={headingId} className="svc-detail">
      <h3 id={headingId} className="visually-hidden">
        {servicesHealthStrings.detailTitle(name)}
      </h3>
      {query.isPending ? <FunctionalState state="loading" /> : null}
      {query.isError ? <FunctionalState state="error" onRetry={() => void query.refetch()} /> : null}
      {detail ? (
        <>
          {state ? (
            <p className="svc-detail__state">
              <HealthBadge state={state.state} />
              <span className="services-page__meta">
                {t("support:status.detail.since", {
                  when: duration((Date.now() - Date.parse(state.since)) / 1000),
                })}
              </span>
            </p>
          ) : null}
          <ul className="svc-detail__figures">
            <li>
              <span>{t("support:status.detail.availability")}</span>
              <strong>
                {availability?.availability === null || availability?.availability === undefined
                  ? "—"
                  : format.percent(availability.availability)}
              </strong>
            </li>
            <li>
              <span>{t("support:status.detail.downtime")}</span>
              <strong>
                {availability?.downtime_seconds
                  ? duration(availability.downtime_seconds)
                  : t("support:status.detail.none")}
              </strong>
            </li>
            <li>
              <span>{t("support:status.detail.unmonitored")}</span>
              <strong>
                {availability?.gap_hours
                  ? t("support:status.detail.hours", { count: availability.gap_hours })
                  : t("support:status.detail.none")}
              </strong>
            </li>
            {sync ? (
              <li>
                <span>{t("support:status.detail.sync")}</span>
                <strong title={sync.last_success_at ? format.dateTime(sync.last_success_at) : undefined}>
                  {sync.status === "running" ? t("support:status.detail.syncing") : ago(sync.last_success_at)}
                </strong>
              </li>
            ) : null}
          </ul>
          <section className="svc-detail__block" aria-label={t("support:status.detail.last48")}>
            <h4>{t("support:status.detail.last48")}</h4>
            <UptimeBars serviceId={serviceId} />
          </section>
          {periods.length ? (
            <section className="svc-detail__block">
              <h4>{t("support:status.detail.changes")}</h4>
              <ol className="svc-timeline">
                {periods.map((period) => (
                  <li key={period.start} data-tone={STATE_TONES[period.state] ?? "none"}>
                    <span className="svc-timeline__dot" aria-hidden="true" />
                    <span className="svc-timeline__text">
                      <strong>{servicesHealthStrings.states[period.state] ?? period.state}</strong>
                      <span className="services-page__meta">
                        {format.dateTime(period.start)} ·{" "}
                        {period.current
                          ? t("support:status.detail.ongoing", { duration: duration(period.seconds) })
                          : duration(period.seconds)}
                      </span>
                    </span>
                  </li>
                ))}
              </ol>
            </section>
          ) : null}
          {incidents.length ? (
            <section className="svc-detail__block">
              <h4>{t("support:status.openIncidents")}</h4>
              <ul className="svc-detail__list">
                {incidents.map((incident) => (
                  <li key={incident.id}>
                    <Icon name="alert" size={16} />
                    <Link to={`/incidents/${incident.id}`}>{incident.title}</Link>
                    <span className="services-page__meta">{t(`support:state.${incident.status}`)}</span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          {maintenance.length ? (
            <section className="svc-detail__block">
              <h4>{t("support:status.plannedMaintenance")}</h4>
              <ul className="svc-detail__list">
                {maintenance.map((window) => (
                  <li key={window.id}>
                    <Icon name="wrench" size={16} />
                    <strong>{window.title}</strong>
                    <span className="services-page__meta">
                      {format.dateTime(window.starts_at)} → {format.dateTime(window.ends_at)}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          {errors.length ? (
            <section className="svc-detail__block">
              <h4>{t("support:status.detail.errors")}</h4>
              <ul className="svc-detail__list">
                {errors.map((error) => (
                  <li key={error.code}>
                    <span className="svc-detail__count">×{error.count}</span>
                    <span>{error.message}</span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          {tickets.length ? (
            <section className="svc-detail__block">
              <h4>{t("support:status.detail.tickets")}</h4>
              <ul className="svc-detail__list">
                {tickets.map((ticket) => (
                  <li key={ticket.id ?? ticket.title}>
                    <Icon name="ticket" size={16} />
                    <span>{ticket.title ?? ticket.label}</span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          {unavailable.length ? (
            <p className="services-page__meta svc-detail__missing">
              <Icon name="info" size={14} />{" "}
              {unavailable.map((u) => u.detail ?? servicesHealthStrings.sectionUnavailable).join(" · ")}
            </p>
          ) : null}
        </>
      ) : null}
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
          const troubled = items.filter(
            (i) => i.degrades_portal !== false && (i.state === "unavailable" || i.state === "degraded"),
          ).length;
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

interface Bucket {
  start: string;
  gap: boolean;
  availability?: number;
}

/**
 * 027: the last 48 hours as a battery of micro-bars — one per hour, green when every check passed, amber
 * when some failed, red when the service was mostly out, grey without checks; each bar tells its hour.
 */
export function UptimeBars({ serviceId }: { serviceId: string }) {
  const t = useT();
  const format = useFormat();
  const history = useQuery({
    queryKey: ["services", serviceId, "uptime48"],
    staleTime: 5 * 60_000,
    retry: false,
    queryFn: async () => {
      const from = new Date(Date.now() - 48 * 3600_000).toISOString();
      const data = (
        await api.GET("/api/v1/services/{service_id}/health/history", {
          params: { path: { service_id: serviceId }, query: { from } },
        })
      ).data as unknown as { buckets?: Bucket[] };
      return Array.isArray(data?.buckets) ? data.buckets.slice(-48) : [];
    },
  });
  const buckets = history.data ?? [];
  if (!buckets.length) return <span className="uptime-bars" data-empty="true" aria-hidden="true" />;
  const level = (b: Bucket) =>
    b.gap || b.availability === undefined
      ? "none"
      : b.availability >= 0.99
        ? "ok"
        : b.availability >= 0.75
          ? "partial"
          : "down";
  const measured = buckets.filter((b) => !b.gap && b.availability !== undefined);
  const mean = measured.length
    ? measured.reduce((sum, b) => sum + (b.availability ?? 0), 0) / measured.length
    : null;
  return (
    <span
      className="uptime-bars"
      role="img"
      aria-label={t("support:status.uptime48", {
        percent: mean === null ? "—" : format.percent(mean),
      })}
    >
      {buckets.map((bucket) => (
        <span
          key={bucket.start}
          data-level={level(bucket)}
          title={`${format.dateTime(bucket.start)} · ${
            bucket.gap || bucket.availability === undefined
              ? t("support:status.noCheck")
              : format.percent(bucket.availability)
          }`}
        />
      ))}
    </span>
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
        <UptimeBars serviceId={item.id} />
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
