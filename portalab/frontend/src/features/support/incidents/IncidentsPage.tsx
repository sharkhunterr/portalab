import { useId } from "react";
import { Link, useParams } from "react-router";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { type Incident, useIncident, useIncidents } from "./api";

/** Incidents (spec 016 T013): open and past incidents, each with its public timeline. Text only. */
function Summary({ incident }: { incident: Incident }) {
  const t = useT();
  const format = useFormat();
  return (
    <>
      <p>
        <span className="incident__severity" data-severity={incident.severity}>
          {t(`support:severity.${incident.severity}`)}
        </span>{" "}
        · {t(`support:state.${incident.state}`)} · {format.dateTime(incident.created_at)}
      </p>
      {incident.services.length ? (
        <p>
          {t("support:incident.services")}:{" "}
          {incident.services.map((s, i) => (
            <span key={s.id}>
              {i ? ", " : ""}
              <Link to={`/services/${s.id}`}>{s.name}</Link>
            </span>
          ))}
        </p>
      ) : null}
    </>
  );
}

export function IncidentDetail({ id }: { id: string }) {
  const t = useT();
  const format = useFormat();
  const headingId = useId();
  const query = useIncident(id);
  if (query.isPending) return <FunctionalState state="loading" />;
  if (query.isError || !query.data)
    return <FunctionalState state="unavailable" onRetry={() => query.refetch()} />;
  const incident = query.data;
  return (
    <article aria-labelledby={headingId} className="incident">
      <h2 id={headingId}>
        {incident.reference} · {incident.title}
      </h2>
      <Summary incident={incident} />
      {incident.summary ? <p>{incident.summary}</p> : null}
      <h3>{t("support:incident.timeline")}</h3>
      <ol className="incident__timeline">
        {[...incident.updates].reverse().map((update) => (
          <li key={update.seq}>
            <strong>{t(`support:state.${update.state}`)}</strong> · {format.dateTime(update.at)}
            <p>{update.message}</p>
          </li>
        ))}
      </ol>
      <Link to="/incidents">{t("support:incident.all")}</Link>
    </article>
  );
}

export function IncidentsList() {
  const t = useT();
  const headingId = useId();
  const all = useIncidents();
  return (
    <section aria-labelledby={headingId}>
      <h2 id={headingId}>{t("support:incident.title")}</h2>
      {all.isPending ? <FunctionalState state="loading" /> : null}
      {all.isError ? <FunctionalState state="unavailable" onRetry={() => all.refetch()} /> : null}
      {all.data && all.data.length === 0 ? <p>{t("support:incident.none")}</p> : null}
      <ul className="incident-list">
        {(all.data ?? []).map((incident) => (
          <li key={incident.id}>
            <Link to={`/incidents/${incident.id}`}>
              {incident.reference} · {incident.title}
            </Link>
            <Summary incident={incident} />
          </li>
        ))}
      </ul>
    </section>
  );
}

export function IncidentsPage() {
  const { incidentId } = useParams();
  return incidentId ? <IncidentDetail id={incidentId} /> : <IncidentsList />;
}

export default IncidentsPage;
