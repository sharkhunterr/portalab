import { type FormEvent, useId, useState } from "react";
import { useAnnounce } from "../../../design-system/a11y/Announce";
import { AdminPage, AdminSection } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, SelectField, TextField } from "../../../design-system/components/Field";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { type Incident, type Severity, useIncidentStaff, useIncidents } from "./api";
import { SeverityBadge, StateSteps } from "./IncidentParts";
import { ServicePicker } from "./ServicePicker";
import "../support.css";

/**
 * Incident console (spec 016 T013): declare, update the public timeline, change severity/services and
 * resolve. Every change sends the incident version (``If-Match``); a concurrent edit is reported.
 */
const SEVERITIES: Severity[] = ["minor", "major", "critical"];
const STATES = ["investigating", "identified", "monitoring"] as const;

function Declare() {
  const t = useT();
  const staff = useIncidentStaff();
  const [title, setTitle] = useState("");
  const [severity, setSeverity] = useState<Severity>("major");
  const [summary, setSummary] = useState("");
  const [services, setServices] = useState<string[]>([]);
  const [banner, setBanner] = useState(false);
  function submit(event: FormEvent) {
    event.preventDefault();
    staff.mutate(
      {
        kind: "create",
        title,
        severity,
        summary,
        service_ids: services,
        banner,
      },
      {
        onSuccess: () => {
          setTitle("");
          setSummary("");
          setServices([]);
          setBanner(false);
        },
      },
    );
  }
  return (
    <AdminSection title={t("support:console.declare")} icon="alert">
      <form onSubmit={submit} className="ds-stack">
        <TextField
          label={t("support:console.title")}
          value={title}
          required
          minLength={3}
          maxLength={200}
          onChange={(e) => setTitle(e.target.value)}
        />
        <SelectField
          label={t("support:console.severity")}
          value={severity}
          onChange={(e) => setSeverity(e.target.value as Severity)}
        >
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>
              {t(`support:severity.${s}`)}
            </option>
          ))}
        </SelectField>
        <TextField
          label={t("support:console.summary")}
          value={summary}
          maxLength={4000}
          onChange={(e) => setSummary(e.target.value)}
        />
        <ServicePicker label={t("support:console.services")} value={services} onChange={setServices} />
        <CheckboxField
          label={t("support:console.banner")}
          hint={t("support:console.bannerHint")}
          checked={banner}
          onChange={(e) => setBanner(e.target.checked)}
        />
        <Button type="submit" disabled={staff.isPending}>
          {t("support:console.declare")}
        </Button>
      </form>
    </AdminSection>
  );
}

function Manage({ incident }: { incident: Incident }) {
  const t = useT();
  const announce = useAnnounce();
  const headingId = useId();
  const staff = useIncidentStaff();
  const [message, setMessage] = useState("");
  const [state, setState] = useState<(typeof STATES)[number]>(
    incident.state === "resolved" ? "monitoring" : incident.state,
  );
  const onError = (error: unknown) => {
    if (error instanceof ApiError && error.code === "incident.version_conflict")
      announce(t("support:console.conflict"));
  };
  const base = { id: incident.id, version: incident.version };
  return (
    <section
      aria-labelledby={headingId}
      className="admin-section incident-manage incident-card"
      data-severity={incident.severity}
    >
      <div className="incident-card__head">
        <SeverityBadge severity={incident.severity} />
        <span className="incident-card__ref">{incident.reference}</span>
      </div>
      <h3 id={headingId} className="incident-card__title">
        {incident.title}
      </h3>
      <StateSteps state={incident.state} />
      <ServicePicker
        label={t("support:console.services")}
        value={incident.services.map((s) => s.id)}
        onChange={(ids) => staff.mutate({ kind: "patch", ...base, service_ids: ids }, { onError })}
      />
      <CheckboxField
        label={t("support:console.banner")}
        hint={t("support:console.bannerHint")}
        checked={incident.banner ?? false}
        disabled={staff.isPending}
        onChange={(e) => staff.mutate({ kind: "patch", ...base, banner: e.target.checked }, { onError })}
      />
      <TextField
        label={t("support:console.message")}
        value={message}
        maxLength={4000}
        onChange={(e) => setMessage(e.target.value)}
      />
      <SelectField
        label={t("support:console.state")}
        value={state}
        onChange={(e) => setState(e.target.value as (typeof STATES)[number])}
      >
        {STATES.map((s) => (
          <option key={s} value={s}>
            {t(`support:state.${s}`)}
          </option>
        ))}
      </SelectField>
      <div className="ds-stack ds-stack--row">
        <Button
          disabled={!message.trim() || staff.isPending}
          onClick={() =>
            staff.mutate(
              { kind: "update", ...base, message, state },
              { onError, onSuccess: () => setMessage("") },
            )
          }
        >
          {t("support:console.post")}
        </Button>
        <SelectField
          label={t("support:console.severity")}
          value={incident.severity}
          onChange={(e) =>
            staff.mutate({ kind: "patch", ...base, severity: e.target.value as Severity }, { onError })
          }
        >
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>
              {t(`support:severity.${s}`)}
            </option>
          ))}
        </SelectField>
        <Button
          variant="danger"
          disabled={staff.isPending}
          onClick={() =>
            staff.mutate(
              { kind: "resolve", ...base, message: message || t("support:console.resolved") },
              { onError },
            )
          }
        >
          {t("support:console.resolve")}
        </Button>
      </div>
    </section>
  );
}

export function IncidentConsole() {
  const t = useT();
  const open = useIncidents("open");
  return (
    <AdminPage
      icon="alert"
      title={t("support:console.title_page")}
      description={t("support:console.description")}
    >
      <Declare />
      {open.isPending ? <FunctionalState state="loading" /> : null}
      {open.isError ? <FunctionalState state="unavailable" onRetry={() => open.refetch()} /> : null}
      {(open.data ?? []).map((incident) => (
        <Manage key={`${incident.id}:${incident.version}`} incident={incident} />
      ))}
    </AdminPage>
  );
}

export default IncidentConsole;
