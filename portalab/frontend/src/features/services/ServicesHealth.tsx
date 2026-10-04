import { useQuery } from "@tanstack/react-query";
import { type ReactNode, useId, useState } from "react";
import { Link } from "react-router";
import { api } from "../../api/client";
import { Icon } from "../../design-system/components/Icon";
import { PageHeader } from "../../design-system/components/PageHeader";
import { FunctionalState } from "../../design-system/FunctionalState";
import { useT } from "../../i18n/hooks/useT";
import { DataRegion } from "../../state/regions";
import { useHasPermission } from "../authz/useMyPermissions";
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

export function ServicesHealth() {
  const [selected, setSelected] = useState<OverviewItem | null>(null);
  const t = useT();
  const manage = useHasPermission("services.manage");
  return (
    <div className="account-page services-page">
      <PageHeader
        level={2}
        icon="server"
        title={servicesHealthStrings.title}
        primary={
          manage ? (
            <Link className="ds-button ds-button--primary" to="/admin/services?add=1">
              <Icon name="plus" size={18} />
              {t("admin:services.add")}
            </Link>
          ) : undefined
        }
      />
      <DataRegion<OverviewItem[]>
        label={servicesHealthStrings.overview}
        queryKey={["services", "health"]}
        queryFn={async () =>
          ((await api.GET("/api/v1/services/health")).data as unknown as { items: OverviewItem[] }).items
        }
      >
        {(items) =>
          items.length === 0 ? (
            <p>{servicesHealthStrings.empty}</p>
          ) : (
            <ul aria-label={servicesHealthStrings.overview} className="services-page__grid">
              {items.map((item) => (
                <li key={item.id} className="ds-card services-page__card" data-state={item.state}>
                  <span className="services-page__name">
                    <Icon name="server" size={20} />
                    <strong>{item.name}</strong>
                  </span>
                  <HealthBadge state={item.state} />
                  <span className="services-page__meta">
                    {servicesHealthStrings.availability(item.availability)}
                  </span>
                  <button
                    type="button"
                    className="ds-button ds-button--secondary"
                    aria-pressed={selected?.id === item.id}
                    onClick={() => setSelected(item)}
                  >
                    {servicesHealthStrings.details(item.name)}
                  </button>
                </li>
              ))}
            </ul>
          )
        }
      </DataRegion>
      {selected ? <ServiceDetail serviceId={selected.id} name={selected.name} /> : null}
    </div>
  );
}
