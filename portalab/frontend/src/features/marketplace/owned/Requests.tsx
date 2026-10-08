import { useState } from "react";
import { StatusBadge } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";
import {
  type MarketRequest,
  type OwnershipRow,
  type RequestField,
  useMyRequests,
  useOwnedActions,
  useProducts,
} from "../api";

/**
 * 027: requests to handle — a special request's form (a film in 4K: which film, Dolby Atmos, languages…)
 * filled once bought, and the member's requests with where they stand (pending, being handled, done or
 * declined — the Coins came back), their deadline and the administrator's note.
 */
export function labelOf(field: RequestField, language: string): string {
  return field.labels[language] ?? field.labels.en ?? Object.values(field.labels)[0] ?? field.key;
}

export function RequestForm({ row }: { row: OwnershipRow }) {
  const t = useT();
  const { locale } = useLocaleContext();
  const language = locale.split("-")[0] ?? "en";
  const { configure } = useOwnedActions();
  const products = useProducts({ category: "", q: "" });
  const product = (products.data ?? []).find((p) => p.key === row.product_key);
  const form = (Array.isArray(product?.preview?.form) ? product.preview.form : []) as RequestField[];
  const [values, setValues] = useState<Record<string, unknown>>({});
  const set = (key: string, value: unknown) => setValues((v) => ({ ...v, [key]: value }));
  const missing = form.some((f) => f.required && !values[f.key]);
  return (
    <form
      className="ds-stack request-form"
      onSubmit={(event) => {
        event.preventDefault();
        configure.mutate({ id: row.id, configuration: values });
      }}
    >
      <p className="ds-field__hint">
        {t("marketplace:request.formHint", { days: Number(product?.preview?.deadline_days ?? 7) })}
      </p>
      {form.map((field) => {
        const label = labelOf(field, language);
        const id = `req-${row.id}-${field.key}`;
        if (field.type === "textarea")
          return (
            <div key={field.key} className="ds-field">
              <label htmlFor={id}>{label}</label>
              <textarea
                id={id}
                rows={3}
                maxLength={2000}
                required={field.required}
                onChange={(e) => set(field.key, e.target.value)}
              />
            </div>
          );
        if (field.type === "choice")
          return (
            <div key={field.key} className="ds-field">
              <label htmlFor={id}>{label}</label>
              <select id={id} required={field.required} onChange={(e) => set(field.key, e.target.value)}>
                <option value="">—</option>
                {field.options.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            </div>
          );
        if (field.type === "multi")
          return (
            <fieldset key={field.key} className="request-form__choices">
              <legend>{label}</legend>
              {field.options.map((o) => (
                <label key={o} className="request-form__choice">
                  <input
                    type="checkbox"
                    onChange={(e) => {
                      const current = (values[field.key] as string[] | undefined) ?? [];
                      set(field.key, e.target.checked ? [...current, o] : current.filter((c) => c !== o));
                    }}
                  />
                  {o}
                </label>
              ))}
            </fieldset>
          );
        if (field.type === "boolean")
          return (
            <label key={field.key} className="request-form__choice">
              <input type="checkbox" onChange={(e) => set(field.key, e.target.checked)} />
              {label}
            </label>
          );
        return (
          <TextField
            key={field.key}
            label={label}
            required={field.required}
            maxLength={300}
            onChange={(e) => set(field.key, e.target.value)}
          />
        );
      })}
      <Button type="submit" disabled={missing || configure.isPending}>
        <Icon name="inbox" size={16} />
        {t("marketplace:request.send")}
      </Button>
    </form>
  );
}

const TONE: Record<string, "info" | "ok" | "warn" | "bad" | "neutral"> = {
  pending: "neutral",
  in_progress: "info",
  done: "ok",
  declined: "bad",
};

/** The details a request carries, by its form's labels (a service's access: the service). */
export function RequestDetails({ request }: { request: MarketRequest }) {
  const t = useT();
  const { locale } = useLocaleContext();
  const language = locale.split("-")[0] ?? "en";
  const fields = request.form as unknown as RequestField[];
  const shown = (value: unknown) =>
    Array.isArray(value)
      ? value.join(", ")
      : typeof value === "boolean"
        ? value
          ? "✓"
          : "—"
        : String(value);
  const rows =
    request.kind === "service"
      ? [{ key: "service", label: t("marketplace:request.service"), value: request.details.service }]
      : fields.map((f) => ({ key: f.key, label: labelOf(f, language), value: request.details[f.key] }));
  return (
    <dl className="request-details">
      {rows
        .filter(
          (r) => r.value !== undefined && r.value !== "" && !(Array.isArray(r.value) && !r.value.length),
        )
        .map((r) => (
          <div key={r.key}>
            <dt>{r.label}</dt>
            <dd>{shown(r.value)}</dd>
          </div>
        ))}
    </dl>
  );
}

export function MyRequests() {
  const t = useT();
  const format = useFormat();
  const requests = useMyRequests();
  if (!requests.data?.length) return null;
  return (
    <section aria-labelledby="my-requests" className="ds-stack">
      <h2 id="my-requests">{t("marketplace:request.mine")}</h2>
      <ul className="ds-stack">
        {requests.data.map((request) => (
          <li key={request.id} className="ds-card ds-stack request-card" data-state={request.state}>
            <div className="request-card__head">
              <strong>{request.product_name}</strong>
              <StatusBadge tone={TONE[request.state] ?? "neutral"}>
                {t(`marketplace:request.state.${request.state}`)}
              </StatusBadge>
            </div>
            <RequestDetails request={request} />
            <p className="admin-muted">
              {request.state === "pending" || request.state === "in_progress"
                ? t("marketplace:request.dueBy", { date: format.date(request.due_at, "long") })
                : request.decided_at
                  ? t("marketplace:request.settledOn", { date: format.date(request.decided_at, "long") })
                  : null}
            </p>
            {request.note ? <p className="request-card__note">{request.note}</p> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
