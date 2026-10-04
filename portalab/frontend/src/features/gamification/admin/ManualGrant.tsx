import { type FormEvent, useState } from "react";
import { AdminSection } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { SelectField, TextField } from "../../../design-system/components/Field";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { useManualGrant, type Value } from "../api";

/**
 * Manual reward (spec 013 T014, ``rewards.grant``): a reason is mandatory; above the threshold the server
 * asks for a confirmation, shown here before the grant is sent again with the confirmation token.
 */
export function ManualGrant() {
  const t = useT();
  const grant = useManualGrant();
  const [form, setForm] = useState({ user_id: "", value: "xp" as Value, amount: 10, reason: "" });
  const [confirmation, setConfirmation] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const send = (token?: string) => {
    setDone(false);
    grant.mutate(
      { ...form, ...(token ? { confirmation: token } : {}) },
      {
        onSuccess: () => {
          setConfirmation(null);
          setDone(true);
        },
        onError: (error) => {
          if (error instanceof ApiError && error.code === "authz.confirmation_required") {
            setConfirmation(String(error.extensions.confirmation ?? ""));
          }
        },
      },
    );
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    send();
  };
  return (
    <AdminSection title={t("gamification:admin.grant.title")} icon="coins">
      <form className="ds-stack" onSubmit={submit}>
        <TextField
          label={t("gamification:admin.grant.user")}
          value={form.user_id}
          required
          onChange={(e) => setForm({ ...form, user_id: e.target.value })}
        />
        <SelectField
          label={t("gamification:admin.grant.value")}
          value={form.value}
          onChange={(e) => setForm({ ...form, value: e.target.value as Value })}
        >
          {(["xp", "contribution", "coins"] as const).map((v) => (
            <option key={v} value={v}>
              {t(`gamification:value.${v}`)}
            </option>
          ))}
        </SelectField>
        <TextField
          label={t("gamification:admin.grant.amount")}
          type="number"
          min={1}
          value={String(form.amount)}
          onChange={(e) => setForm({ ...form, amount: Number(e.target.value) })}
        />
        <TextField
          label={t("gamification:admin.grant.reason")}
          value={form.reason}
          required
          minLength={3}
          onChange={(e) => setForm({ ...form, reason: e.target.value })}
        />
        <Button type="submit" disabled={grant.isPending}>
          {t("gamification:admin.grant.submit")}
        </Button>
      </form>
      {confirmation ? (
        <div role="alertdialog" aria-labelledby="gamification-grant-confirm" className="ds-card">
          <p id="gamification-grant-confirm">{t("gamification:admin.grant.confirm")}</p>
          <Button onClick={() => send(confirmation)}>{t("gamification:admin.grant.submit")}</Button>
        </div>
      ) : null}
      {done ? <p role="status">{t("gamification:admin.grant.done")}</p> : null}
    </AdminSection>
  );
}
