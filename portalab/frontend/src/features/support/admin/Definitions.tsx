import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../../api/client";
import {
  AdminPage,
  AdminSection,
  AdminTable,
  AdminTabs,
  FormActions,
  JsonField,
} from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { Dialog } from "../../../design-system/components/Overlays";
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
    <div className="admin-form admin-dialog-body">
      <JsonField id={`edit-${kind}-${itemKey}`} label={itemKey} value={text} onChange={setText} rows={16} />
      {save.isSuccess ? <p role="status">{t("support:admin.saved")}</p> : null}
      {save.isError ? (
        <ul role="alert" className="admin-errors">
          {(errors.length ? errors : [t("support:admin.invalid")]).map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      ) : null}
      <FormActions>
        <Button onClick={() => save.mutate()}>{t("support:admin.save")}</Button>
      </FormActions>
    </div>
  );
}

export function Definitions() {
  const t = useT();
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
  const items = (list.data ?? []).map((item) => {
    const { key, version, updated_at, ...rest } = item as {
      key: string;
      version?: number;
      updated_at?: string;
      label?: string;
      fields?: unknown[];
    };
    const initial = kind === "workflows" ? (rest as { definition: unknown }).definition : rest;
    return { key, version, rest, initial };
  });
  return (
    <AdminPage
      icon="lifebuoy"
      title={t("support:admin.title")}
      description={t("support:admin.description")}
      tabs={
        <AdminTabs
          label={t("support:admin.title")}
          current={kind}
          onChange={(k) => setKind(k as Kind)}
          tabs={(["types", "workflows", "forms"] as Kind[]).map((k) => ({
            key: k,
            label: t(`support:admin.${k}`),
          }))}
        />
      }
    >
      {list.isError ? <FunctionalState state="unauthorized" /> : null}
      <AdminSection title={t(`support:admin.${kind}`)} icon="list" flush>
        <AdminTable
          label={t(`support:admin.${kind}`)}
          rows={items}
          rowKey={(item) => item.key}
          empty={<p className="admin-muted admin-pad">{t("support:admin.empty")}</p>}
          columns={[
            {
              key: "key",
              header: t("support:admin.key"),
              primary: true,
              render: (item) => (
                <span className="services-admin__name">
                  <strong>{String((item.rest as { label?: string }).label ?? item.key)}</strong>
                  <code className="admin-muted">{item.key}</code>
                </span>
              ),
            },
            {
              key: "version",
              header: t("support:admin.version"),
              render: (item) => (item.version !== undefined ? `v${item.version}` : "—"),
            },
            {
              key: "fields",
              header: t("support:admin.fields"),
              render: (item) => {
                const fields = (item.rest as { fields?: unknown[] }).fields;
                return Array.isArray(fields) ? fields.length : "—";
              },
            },
          ]}
          actions={(item) => (
            <Dialog
              size="lg"
              title={String((item.rest as { label?: string }).label ?? item.key)}
              closeLabel={t("support:admin.close")}
              trigger={
                <Button variant="secondary">
                  {t("support:admin.edit")}
                  <span className="visually-hidden"> {item.key}</span>
                </Button>
              }
            >
              <Editor
                key={`${kind}-${item.key}-${item.version ?? 0}`}
                kind={kind}
                itemKey={item.key}
                initial={item.initial}
              />
            </Dialog>
          )}
        />
      </AdminSection>
    </AdminPage>
  );
}

export default Definitions;
