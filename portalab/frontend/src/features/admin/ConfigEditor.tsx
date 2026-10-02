import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { api } from "../../api/client";
import { ApiError, DataRegion } from "../../state/regions";
import { adminStrings as t } from "./strings";

interface SettingItem {
  key: string;
  description: string;
  sensitive: boolean;
  value: unknown;
  source: string;
}

interface PreviewResult {
  ok: boolean;
  diff: { key: string; before: unknown; after: unknown }[];
  warnings: string[];
  errors: { key: string; detail: string }[];
}

function parse(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

function SettingRow({ item }: { item: SettingItem }) {
  const fieldId = useId();
  const queryClient = useQueryClient();
  const [raw, setRaw] = useState("");
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const body = {
    changes: [{ key: item.key, value: parse(raw), scope: "global" as const, scope_ref: "", unset: false }],
    reason: "",
  };
  const validate = useMutation({
    mutationFn: async () =>
      (await api.POST("/api/v1/admin/config/validate", { body })).data as unknown as PreviewResult,
    onSuccess: setPreview,
  });
  const apply = useMutation({
    mutationFn: async () => {
      await api.PUT("/api/v1/admin/config", { body });
    },
    onSuccess: () => {
      setPreview(null);
      void queryClient.invalidateQueries({ queryKey: ["admin", "config"] });
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    validate.mutate();
  }

  return (
    <tr>
      <th scope="row">
        {item.key}
        <p className="field-hint">{item.description}</p>
      </th>
      <td>{item.sensitive ? t.sensitiveValue : JSON.stringify(item.value)}</td>
      <td>{item.source}</td>
      <td>
        <form onSubmit={submit}>
          <label htmlFor={fieldId} className="sr-only">
            {t.newValue(item.key)}
          </label>
          <input id={fieldId} value={raw} onChange={(event) => setRaw(event.target.value)} />
          <button type="submit">{t.preview}</button>
        </form>
        {preview ? (
          <div role="status">
            {preview.ok ? (
              <>
                <p>
                  {t.before}: {JSON.stringify(preview.diff[0]?.before)} → {t.after}:{" "}
                  {JSON.stringify(preview.diff[0]?.after)}
                </p>
                {preview.warnings.map((warning) => (
                  <p key={warning}>{warning}</p>
                ))}
                <button type="button" onClick={() => apply.mutate()} disabled={apply.isPending}>
                  {t.apply}
                </button>
              </>
            ) : (
              <p role="alert">{preview.errors[0]?.detail ?? t.invalid}</p>
            )}
          </div>
        ) : null}
        {apply.isError ? (
          <p role="alert">{apply.error instanceof ApiError ? apply.error.message : t.genericError}</p>
        ) : null}
        {apply.isSuccess ? <p role="status">{t.applied}</p> : null}
      </td>
    </tr>
  );
}

/** Configuration editor (spec 020 US5): preview first, then apply; sensitive values are write-only. */
export function ConfigEditor() {
  return (
    <DataRegion<SettingItem[]>
      label={t.configTitle}
      queryKey={["admin", "config"]}
      queryFn={async () =>
        ((await api.GET("/api/v1/admin/config")).data as unknown as { settings: SettingItem[] }).settings
      }
    >
      {(settings) => (
        <div className="account-page">
          <h2>{t.configTitle}</h2>
          <table>
            <thead>
              <tr>
                <th scope="col">{t.setting}</th>
                <th scope="col">{t.value}</th>
                <th scope="col">{t.source}</th>
                <th scope="col">{t.newValue("…")}</th>
              </tr>
            </thead>
            <tbody>
              {settings.map((item) => (
                <SettingRow key={item.key} item={item} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </DataRegion>
  );
}
