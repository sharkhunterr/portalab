import { useMutation } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { api } from "../../api/client";
import { ApiError } from "../../state/regions";
import { adminStrings as t } from "./strings";

type Kind = "module" | "plugin" | "connector" | "service" | "automation";
const KINDS: Kind[] = ["module", "plugin", "connector", "service", "automation"];

/** Enable/disable extensions (spec 020 US6); data is never deleted, re-enabling restores. */
export function Toggles() {
  const ids = { kind: useId(), ref: useId(), title: useId() };
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
    <form aria-labelledby={ids.title} className="auth-form" onSubmit={(event) => submit(event, true)}>
      <h2 id={ids.title}>{t.togglesTitle}</h2>
      {mutation.isError ? (
        <p role="alert">
          {mutation.error instanceof ApiError && mutation.error.code === "admin.enable_refused"
            ? t.refused
            : t.genericError}
        </p>
      ) : null}
      {mutation.data ? <p role="status">{t.toggled(mutation.data.ref, mutation.data.enabled)}</p> : null}
      <label htmlFor={ids.kind}>{t.kindField}</label>
      <select id={ids.kind} value={kind} onChange={(event) => setKind(event.target.value as Kind)}>
        {KINDS.map((value) => (
          <option key={value} value={value}>
            {value}
          </option>
        ))}
      </select>
      <label htmlFor={ids.ref}>{t.refField}</label>
      <input id={ids.ref} required value={ref} onChange={(event) => setRef(event.target.value)} />
      <button type="submit">{t.enable}</button>
      <button type="button" onClick={(event) => submit(event, false)}>
        {t.disable}
      </button>
    </form>
  );
}
