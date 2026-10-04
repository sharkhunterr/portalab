import { useMutation } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { api } from "../../api/client";
import { AdminSection, FormActions, FormGrid } from "../../design-system/admin/AdminKit";
import { Button } from "../../design-system/components/Button";
import { SelectField, TextField } from "../../design-system/components/Field";
import { useT } from "../../i18n/hooks/useT";
import { ApiError } from "../../state/regions";

type Kind = "module" | "plugin" | "connector" | "service" | "automation";
const KINDS: Kind[] = ["module", "plugin", "connector", "service", "automation"];

/** Enable/disable extensions (spec 020 US6); data is never deleted, re-enabling restores. */
export function Toggles() {
  const t = useT();
  const [kind, setKind] = useState<Kind>("plugin");
  const [ref, setRef] = useState("");
  const mutation = useMutation({
    mutationFn: async (enabled: boolean) =>
      (
        await api.POST("/api/v1/admin/toggles/{kind}/{ref}", {
          params: { path: { kind, ref } },
          body: { enabled, reason: "" },
        })
      ).data as unknown as { ref: string; enabled: boolean },
  });

  function submit(event: FormEvent, enabled: boolean) {
    event.preventDefault();
    mutation.mutate(enabled);
  }

  return (
    <AdminSection title={t("admin:toggles.title")} description={t("admin:toggles.description")} icon="plug">
      <form className="admin-form" onSubmit={(event) => submit(event, true)}>
        {mutation.isError ? (
          <p role="alert">
            {mutation.error instanceof ApiError && mutation.error.code === "admin.enable_refused"
              ? t("admin:toggles.refused")
              : t("admin:config.failed")}
          </p>
        ) : null}
        {mutation.data ? (
          <p role="status">
            {t(mutation.data.enabled ? "admin:toggles.enabled" : "admin:toggles.disabled", {
              ref: mutation.data.ref,
            })}
          </p>
        ) : null}
        <FormGrid>
          <SelectField
            label={t("admin:toggles.kind")}
            value={kind}
            onChange={(e) => setKind(e.target.value as Kind)}
          >
            {KINDS.map((value) => (
              <option key={value} value={value}>
                {t(`admin:toggles.kinds.${value}`)}
              </option>
            ))}
          </SelectField>
          <TextField
            label={t("admin:toggles.ref")}
            required
            value={ref}
            onChange={(e) => setRef(e.target.value)}
          />
        </FormGrid>
        <FormActions>
          <Button type="button" variant="secondary" onClick={(event) => submit(event, false)}>
            {t("admin:toggles.disable")}
          </Button>
          <Button type="submit">{t("admin:toggles.enable")}</Button>
        </FormActions>
      </form>
    </AdminSection>
  );
}
