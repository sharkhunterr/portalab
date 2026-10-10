import { type FormEvent, useId, useState } from "react";
import "../support.css";
import { Link, useNavigate } from "react-router";
import { api } from "../../../api/client";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, SelectField, TextField } from "../../../design-system/components/Field";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { type FieldDef, type PrecheckResult, precheck, useTicketActions, useTicketTypes } from "./api";
import { DiagnosisPanel } from "./DiagnosisPanel";
import { FieldInputs } from "./FieldInputs";
import { ServicePicker } from "./ServicePicker";

/**
 * New ticket (spec 016 T025/T028): describe → precheck (open incidents and wiki suggestions, no AI) →
 * optional assistant diagnosis (prefills a draft) → the form; the user always submits explicitly.
 * 027 (#25): the form alone, shared by the page and the dashboard's « new ticket » dialog.
 */
export function NewTicketForm({
  onCreated,
  formId,
}: {
  onCreated: (ticket: { id: string }) => void;
  /** #25: in a dialog, the send button sits in its footer (``form={formId}``) beside « Close » */
  formId?: string;
}) {
  const t = useT();
  const headingId = useId();
  const generated = useId();
  const form = formId ?? generated;
  const types = useTicketTypes();
  const { create } = useTicketActions("");
  const [typeKey, setTypeKey] = useState("");
  const [serviceId, setServiceId] = useState("");
  const [problem, setProblem] = useState("");
  const [checked, setChecked] = useState<PrecheckResult | null>(null);
  const [incident, setIncident] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [draftId, setDraftId] = useState<string | null>(null);
  const type = types.data?.find((x) => x.key === typeKey);
  const runPrecheck = async () => setChecked(await precheck(serviceId || undefined, problem));
  const loadDraft = async (id: string) => {
    const { data } = await api.GET("/api/v1/tickets/drafts/{draft_id}", {
      params: { path: { draft_id: id } },
    });
    if (!data) return;
    const payload = data.payload as {
      type_key?: string;
      title?: string;
      description?: string;
      fields?: Record<string, unknown>;
    };
    if (payload.type_key) setTypeKey(payload.type_key);
    setTitle(payload.title ?? "");
    setProblem(payload.description ?? problem);
    setValues(payload.fields ?? {});
    setDraftId(id);
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate(
      {
        type_key: typeKey,
        title,
        description: problem,
        fields: values,
        priority: "normal",
        ...(serviceId ? { service_id: serviceId } : {}),
        ...(incident ? { incident_id: incident } : {}),
        ...(draftId ? { draft_id: draftId } : {}),
      },
      { onSuccess: (ticket) => onCreated(ticket) },
    );
  };
  const missing =
    create.error instanceof ApiError ? ((create.error.extensions.fields as string[] | undefined) ?? []) : [];
  // #27: the title first; fields outside the <form> belong to it through ``form``, so « required » holds
  return (
    <div className="new-ticket">
      <TextField
        label={`${t("support:new.ticketTitle")} *`}
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        form={form}
        required
      />
      <SelectField
        form={form}
        label={t("support:new.type")}
        value={typeKey}
        onChange={(e) => setTypeKey(e.target.value)}
        required
      >
        <option value="">—</option>
        {(types.data ?? []).map((x) => (
          <option key={x.key} value={x.key}>
            {x.label}
          </option>
        ))}
      </SelectField>
      <ServicePicker value={serviceId} onChange={setServiceId} />
      <div className="ds-field">
        <label htmlFor={`${headingId}-problem`}>{t("support:new.problem")}</label>
        <textarea
          id={`${headingId}-problem`}
          rows={5}
          value={problem}
          onChange={(e) => setProblem(e.target.value)}
        />
      </div>
      <div className="ds-stack ds-stack--row">
        <Button variant="secondary" onClick={() => void runPrecheck()} disabled={!problem.trim()}>
          {t("support:new.check")}
        </Button>
        <DiagnosisPanel
          problem={problem}
          serviceId={serviceId || undefined}
          onDraft={(id) => void loadDraft(id)}
        />
      </div>
      {checked ? (
        <section aria-label={t("support:new.before")}>
          {checked.incidents.items.length ? (
            <>
              <h3>{t("support:new.incidents")}</h3>
              <ul>
                {checked.incidents.items.map((i) => (
                  <li key={i.id}>
                    <Link to={i.url}>
                      {i.reference} · {i.title}
                    </Link>
                    <CheckboxField
                      label={t("support:new.linkIncident")}
                      checked={incident === i.id}
                      onChange={(e) => setIncident(e.target.checked ? i.id : null)}
                    />
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          {checked.knowledge.state === "unavailable" ? (
            <FunctionalState state="unavailable" label={t("support:new.wikiUnavailable")} />
          ) : checked.knowledge.items.length ? (
            <>
              <h3>{t("support:new.wiki")}</h3>
              <ul>
                {checked.knowledge.items.map((k) => (
                  <li key={k.url}>
                    <Link to={k.url}>{k.title}</Link> — {k.excerpt}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </section>
      ) : null}
      {draftId ? <p role="status">{t("support:new.draftLoaded")}</p> : null}
      <form onSubmit={submit} id={form}>
        {type ? (
          <FieldInputs
            defs={type.fields as unknown as FieldDef[]}
            values={values}
            onChange={setValues}
            errors={missing}
          />
        ) : null}
        {formId ? null : (
          <Button type="submit" data-tour="ticket-submit" disabled={!typeKey || !title || create.isPending}>
            {t("support:new.submit")}
          </Button>
        )}
        {create.isError ? (
          <p role="alert">
            {missing.length
              ? t("support:new.missing", { fields: missing.join(", ") })
              : t("support:new.failed")}
          </p>
        ) : null}
      </form>
    </div>
  );
}

export function NewTicket() {
  const t = useT();
  const navigate = useNavigate();
  const headingId = useId();
  return (
    <section aria-labelledby={headingId}>
      <PageHeader titleId={headingId} level={2} icon="ticket" title={t("support:new.title")} />
      <NewTicketForm onCreated={(ticket) => navigate(`/support/tickets/${ticket.id}`)} />
    </section>
  );
}

export default NewTicket;
