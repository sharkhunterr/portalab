import { useId, useState } from "react";
import { Link, useParams } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { EmptyState, Skeleton } from "../../../design-system/components/Placeholders";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { type Incident, useIncident, useIncidents } from "./api";
import { SeverityBadge, StateSteps, useLasting } from "./IncidentParts";
import { type Maintenance, useMaintenances, useServiceNames } from "./maintenance";

/** Incidents (spec 016 T013; 027 redesign): the state of the portal at a glance, then each incident as a
 * card — severity, step reached, how long it lasts, affected services, latest news — and its timeline. */
function Card({ incident }: { incident: Incident }) {
  const t = useT();
  const format = useFormat();
  const lasting = useLasting();
  const latest = incident.updates.at(-1);
  const resolved = incident.state === "resolved";
  return (
    <li className="incident-card" data-severity={incident.severity} data-resolved={resolved || undefined}>
      <div className="incident-card__head">
        <SeverityBadge severity={incident.severity} />
        <span className="incident-card__ref">{incident.reference}</span>
        <span className="incident-card__lasting">
          <Icon name="clock" size={12} />
          {resolved
            ? t("support:incident.lasted", { duration: lasting(incident.created_at, incident.resolved_at) })
            : t("support:incident.since", { duration: lasting(incident.created_at) })}
        </span>
      </div>
      <h3 className="incident-card__title">
        <Link to={`/incidents/${incident.id}`}>{incident.title}</Link>
      </h3>
      <StateSteps state={incident.state} />
      {latest ? (
        <p className="incident-card__latest">
          <strong>{t(`support:state.${latest.state}`)}</strong> · {format.dateTime(latest.at)} —{" "}
          {latest.message}
        </p>
      ) : incident.summary ? (
        <p className="incident-card__latest">{incident.summary}</p>
      ) : null}
      {incident.services.length ? (
        <ul className="incident-card__services" aria-label={t("support:incident.services")}>
          {incident.services.map((s) => (
            <li key={s.id}>
              <Link to={`/services/${s.id}`}>
                <Icon name="server" size={12} />
                {s.name}
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}

export function IncidentDetail({ id }: { id: string }) {
  const t = useT();
  const format = useFormat();
  const lasting = useLasting();
  const headingId = useId();
  const query = useIncident(id);
  if (query.isPending) return <FunctionalState state="loading" />;
  if (query.isError || !query.data)
    return <FunctionalState state="unavailable" onRetry={() => query.refetch()} />;
  const incident = query.data;
  const resolved = incident.state === "resolved";
  return (
    <article aria-labelledby={headingId} className="incident">
      <Link to="/incidents" className="incident__back">
        <Icon name="chevron-left" size={16} />
        {t("support:incident.all")}
      </Link>
      <PageHeader
        titleId={headingId}
        level={2}
        icon="alert"
        title={incident.title}
        context={incident.reference}
      />
      <section className="incident-card incident-card--hero" data-severity={incident.severity}>
        <div className="incident-card__head">
          <SeverityBadge severity={incident.severity} />
          <span className="incident-card__lasting">
            <Icon name="clock" size={12} />
            {resolved
              ? t("support:incident.lasted", { duration: lasting(incident.created_at, incident.resolved_at) })
              : t("support:incident.since", { duration: lasting(incident.created_at) })}
          </span>
        </div>
        <StateSteps state={incident.state} />
        {incident.summary ? <p className="incident-card__summary">{incident.summary}</p> : null}
        {incident.services.length ? (
          <ul className="incident-card__services" aria-label={t("support:incident.services")}>
            {incident.services.map((s) => (
              <li key={s.id}>
                <Link to={`/services/${s.id}`}>
                  <Icon name="server" size={12} />
                  {s.name}
                </Link>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
      <h3>{t("support:incident.timeline")}</h3>
      <ol className="incident-timeline">
        {[...incident.updates].reverse().map((update) => (
          <li key={update.seq} data-state={update.state}>
            <span className="incident-timeline__dot" aria-hidden="true" />
            <div>
              <p className="incident-timeline__head">
                <strong>{t(`support:state.${update.state}`)}</strong>
                <time dateTime={update.at}>{format.dateTime(update.at)}</time>
              </p>
              <p>{update.message}</p>
            </div>
          </li>
        ))}
        <li data-state="created">
          <span className="incident-timeline__dot" aria-hidden="true" />
          <div>
            <p className="incident-timeline__head">
              <strong>{t("support:incident.declared")}</strong>
              <time dateTime={incident.created_at}>{format.dateTime(incident.created_at)}</time>
            </p>
          </div>
        </li>
      </ol>
    </article>
  );
}

/** A planned maintenance (027): shown with the incidents — when, how long, what it touches. */
function MaintenanceCard({ item, names }: { item: Maintenance; names: Map<string, string> | undefined }) {
  const t = useT();
  const format = useFormat();
  const lasting = useLasting();
  const running = Date.parse(item.starts_at) <= Date.now();
  return (
    <li className="incident-card incident-card--maintenance" data-running={running || undefined}>
      <div className="incident-card__head">
        <span className="incident-severity" data-severity="maintenance">
          <Icon name="wrench" size={12} />
          {t(running ? "support:maintenance.running" : "support:maintenance.planned")}
        </span>
        <span className="incident-card__lasting">
          <Icon name="clock" size={12} />
          {lasting(item.starts_at, item.ends_at)}
        </span>
      </div>
      <h3 className="incident-card__title">{item.title}</h3>
      <p className="incident-card__latest">
        {format.dateTime(item.starts_at)} → {format.dateTime(item.ends_at)}
      </p>
      {item.description ? <p className="incident-card__summary">{item.description}</p> : null}
      <ul className="incident-card__services">
        <li>
          {item.service_id ? (
            <Link to={`/services/${item.service_id}`}>
              <Icon name="server" size={12} />
              {names?.get(item.service_id) ?? item.service_id}
            </Link>
          ) : (
            <span className="incident-card__whole">
              <Icon name="server" size={12} />
              {t("support:console.wholeServer")}
            </span>
          )}
        </li>
      </ul>
    </li>
  );
}

type Filter = "open" | "resolved" | "all";

export function IncidentsList() {
  const t = useT();
  const headingId = useId();
  const all = useIncidents();
  const maintenances = useMaintenances();
  const names = useServiceNames(Boolean(maintenances.data?.length));
  const [filter, setFilter] = useState<Filter>("open");
  const items = all.data ?? [];
  const open = items.filter((i) => i.state !== "resolved");
  const recent = items.filter(
    (i) =>
      i.state === "resolved" && i.resolved_at && Date.now() - Date.parse(i.resolved_at) < 30 * 86_400_000,
  );
  const shown =
    filter === "all" ? items : filter === "open" ? open : items.filter((i) => i.state === "resolved");
  return (
    <section aria-labelledby={headingId} className="incidents-page">
      <PageHeader
        titleId={headingId}
        level={2}
        icon="alert"
        title={t("support:incident.title")}
        context={t("support:incident.intro")}
      />
      {all.isPending ? <Skeleton shape="tile" count={2} label={t("support:incident.title")} /> : null}
      {all.isError ? <FunctionalState state="unavailable" onRetry={() => all.refetch()} /> : null}
      {all.data ? (
        <div className="incidents-status" data-ok={open.length === 0 || undefined}>
          <span className="incidents-status__icon" aria-hidden="true">
            <Icon name={open.length ? "alert" : "check"} size={26} />
          </span>
          <div>
            <strong>
              {open.length
                ? t("support:incident.count", { count: open.length })
                : t("support:incident.allGood")}
            </strong>
            <span>{t("support:incident.resolvedRecently", { count: recent.length })}</span>
          </div>
        </div>
      ) : null}
      {items.length ? (
        <fieldset className="ds-subnav" aria-label={t("support:incident.filter")}>
          {(["open", "resolved", "all"] as Filter[]).map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={filter === value}
              onClick={() => setFilter(value)}
            >
              {t(`support:incident.filter.${value}`)}
            </button>
          ))}
        </fieldset>
      ) : null}
      {all.data && shown.length === 0 ? (
        <EmptyState
          icon="check"
          title={t(items.length ? "support:incident.noneHere" : "support:incident.none")}
          action={
            <Link className="ds-button ds-button--secondary" to="/services">
              {t("support:incident.toServices")}
            </Link>
          }
        />
      ) : null}
      <ul className="incident-cards">
        {shown.map((incident) => (
          <Card key={incident.id} incident={incident} />
        ))}
      </ul>
      {maintenances.data?.length ? (
        <section className="incidents-maintenance" aria-label={t("support:maintenance.title")}>
          <h3>
            <Icon name="wrench" size={18} />
            {t("support:maintenance.title")}
          </h3>
          <ul className="incident-cards">
            {maintenances.data.map((item) => (
              <MaintenanceCard key={item.id} item={item} names={names.data} />
            ))}
          </ul>
        </section>
      ) : null}
    </section>
  );
}

export function IncidentsPage() {
  const { incidentId } = useParams();
  return incidentId ? <IncidentDetail id={incidentId} /> : <IncidentsList />;
}

export default IncidentsPage;
