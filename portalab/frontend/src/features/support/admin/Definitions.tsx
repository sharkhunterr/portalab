import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { api } from "../../../api/client";
import { Button } from "../../../design-system/components/Button";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";

/**
 * Support configuration (spec 016 T026): ticket types (custom fields), workflows (versioned; validated by the
 * server, errors listed) and feedback forms, edited as structured JSON. ``support.configure`` only.
 */
type Kind = "types" | "workflows" | "forms";

function Editor({ kind, itemKey, initial }: { kind: Kind; itemKey: string; initial: unknown }) {
  const t = useT();
  const client = useQueryClient();
  const [text, setText] = useState(JSON.stringify(initial, null, 2));
  const save = useMutation({
    mutationFn: async () => {
      const body = JSON.parse(text) as never;
      const path = { params: { path: { key: itemKey } } };
      if (kind === "types")
        return (await api.PUT("/api/v1/admin/support/types/{key}", { ...path, body })).data;
      if (kind === "forms")
        return (await api.PUT("/api/v1/admin/support/forms/{key}", { ...path, body })).data;
      return (await api.PUT("/api/v1/admin/support/workflows/{key}", { ...path, body: { definition: body } }))
        .data;
    },
    onSettled: () => client.invalidateQueries({ queryKey: ["support", "admin"] }),
  });
  const errors =
    save.error instanceof ApiError ? ((save.error.extensions.errors as string[] | undefined) ?? []) : [];
  return (
    <div>
      <label htmlFor={`edit-${kind}-${itemKey}`}>{itemKey}</label>
      <textarea
        id={`edit-${kind}-${itemKey}`}
        rows={12}
        className="markdown-editor__input"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <Button onClick={() => save.mutate()}>{t("support:admin.save")}</Button>
      {save.isSuccess ? <p role="status">{t("support:admin.saved")}</p> : null}
      {save.isError ? (
        <ul role="alert">
          {(errors.length ? errors : [t("support:admin.invalid")]).map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export function Definitions() {
  const t = useT();
  const headingId = useId();
  const [kind, setKind] = useState<Kind>("types");
  const list = useQuery({
    queryKey: ["support", "admin", kind],
    retry: false,
    queryFn: async () => {
      if (kind === "types")
        return ((await api.GET("/api/v1/admin/support/types")).data ?? []) as Array<Record<string, unknown>>;
      if (kind === "forms")
        return ((await api.GET("/api/v1/admin/support/forms")).data ?? []) as Array<Record<string, unknown>>;
      return ((await api.GET("/api/v1/admin/support/workflows")).data ?? []) as Array<
        Record<string, unknown>
      >;
    },
  });
  return (
    <section aria-labelledby={headingId}>
      <PageHeader titleId={headingId} level={2} icon="lifebuoy" title={t("support:admin.title")} />
      <div className="ds-stack ds-stack--row" role="toolbar" aria-label={t("support:admin.title")}>
        {(["types", "workflows", "forms"] as Kind[]).map((k) => (
          <Button
            key={k}
            variant={k === kind ? "primary" : "secondary"}
            aria-pressed={k === kind}
            onClick={() => setKind(k)}
          >
            {t(`support:admin.${k}`)}
          </Button>
        ))}
      </div>
      {list.isError ? <FunctionalState state="unauthorized" /> : null}
      {(list.data ?? []).map((item) => {
        const { key, version, updated_at, ...rest } = item as {
          key: string;
          version?: number;
          updated_at?: string;
        };
        const initial = kind === "workflows" ? (rest as { definition: unknown }).definition : rest;
        return <Editor key={`${kind}-${key}-${version ?? 0}`} kind={kind} itemKey={key} initial={initial} />;
      })}
    </section>
  );
}

export default Definitions;
