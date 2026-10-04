import { type FormEvent, useId, useState } from "react";
import { useSearchParams } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { SelectField } from "../../../design-system/components/Field";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { type FieldDef, useFeedbackForms, useSubmitFeedback } from "../tickets/api";
import { FieldInputs } from "../tickets/FieldInputs";

/** Feedback (spec 016 T030): choose a form, fill it, send — it is reviewed by staff, never a ticket by itself. */
export function FeedbackPage() {
  const t = useT();
  const headingId = useId();
  const [params] = useSearchParams();
  const forms = useFeedbackForms();
  const submit = useSubmitFeedback();
  const [key, setKey] = useState(params.get("form") ?? "general");
  const [values, setValues] = useState<Record<string, unknown>>({});
  const form = forms.data?.find((f) => f.key === key);
  const missing =
    submit.error instanceof ApiError ? ((submit.error.extensions.fields as string[] | undefined) ?? []) : [];
  const send = (event: FormEvent) => {
    event.preventDefault();
    submit.mutate({ form_key: key, values });
  };
  return (
    <section aria-labelledby={headingId}>
      <PageHeader titleId={headingId} level={2} icon="message" title={t("support:feedback.title")} />
      {submit.isSuccess ? (
        <p role="status">{t("support:feedback.thanks")}</p>
      ) : (
        <form onSubmit={send}>
          <SelectField
            label={t("support:feedback.kind")}
            value={key}
            onChange={(e) => {
              setKey(e.target.value);
              setValues({});
            }}
          >
            {(forms.data ?? []).map((f) => (
              <option key={f.key} value={f.key}>
                {f.label}
              </option>
            ))}
          </SelectField>
          {form ? (
            <FieldInputs
              defs={form.fields as unknown as FieldDef[]}
              values={values}
              onChange={setValues}
              errors={missing}
            />
          ) : null}
          <Button type="submit">{t("support:feedback.send")}</Button>
          {submit.isError ? <p role="alert">{t("support:feedback.failed")}</p> : null}
        </form>
      )}
    </section>
  );
}

export default FeedbackPage;
