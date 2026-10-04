import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { api } from "../../../api/client";
import { useAnnounce } from "../../../design-system/a11y/Announce";
import {
  AdminPage,
  AdminSection,
  AdminTable,
  AdminTabs,
  FormActions,
  JsonField,
  StatusBadge,
} from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";

/**
 * Statistic definitions (spec 017 T017; admin): the closed-set document is edited as validated JSON (the
 * server rejects anything outside the schema and lists why); activation and rebuild ask for a confirmation.
 */
interface Row {
  key: string;
  status: string;
  active_version: number | null;
  latest_version: number;
  domain: string | null;
  definition: Record<string, unknown> | null;
  change_policy: string | null;
}

export function DefinitionsAdmin() {
  const t = useT();
  const announce = useAnnounce();
  const client = useQueryClient();
  const editorId = useId();
  const list = useQuery({
    queryKey: ["statistics", "admin"],
    queryFn: async () =>
      ((await api.GET("/api/v1/admin/statistics/definitions")).data ?? []) as unknown as Row[],
  });
  const [draft, setDraft] = useState("");
  const [errors, setErrors] = useState<string[]>([]);
  const refresh = () => client.invalidateQueries({ queryKey: ["statistics"] });
  const save = useMutation({
    mutationFn: async () => {
      const definition = JSON.parse(draft) as Record<string, unknown>;
      await api.POST("/api/v1/admin/statistics/definitions", {
        body: { definition, change_policy: "forward_only" },
      });
    },
    onSuccess: () => {
      setErrors([]);
      announce(t("statistics:admin.saved"));
      void refresh();
    },
    onError: (error) => {
      if (error instanceof SyntaxError) setErrors([t("statistics:admin.invalidJson")]);
      else if (error instanceof ApiError)
        setErrors(((error.extensions.errors as string[]) ?? [error.message]).map(String));
    },
  });
  async function confirmed(path: "activate" | "rebuild", key: string) {
    const url = `/api/v1/admin/statistics/definitions/{key}/${path}` as const;
    const call = (confirmation?: string) =>
      api.POST(url as "/api/v1/admin/statistics/definitions/{key}/activate", {
        params: { path: { key } },
        body: confirmation ? { confirmation, reason: "" } : { reason: "" },
      });
    try {
      await call();
    } catch (error) {
      if (error instanceof ApiError && error.code === "authz.confirmation_required") {
        if (window.confirm(t(`statistics:admin.confirm.${path}`, { key }))) {
          await call(String(error.extensions.confirmation));
          announce(t("statistics:admin.done"));
        }
      } else throw error;
    }
    await refresh();
  }
  const rows = list.data ?? [];
  const domains = [...new Set(rows.map((row) => row.key.split(".")[0] ?? row.key))].sort();
  const [domain, setDomain] = useState("all");
  const shown = rows.filter((row) => domain === "all" || row.key.startsWith(`${domain}.`));
  return (
    <AdminPage
      icon="chart"
      title={t("statistics:admin.title")}
      description={t("statistics:admin.description")}
      primary={
        <Button
          onClick={() => {
            setDraft(NEW_DEFINITION);
            document.getElementById(editorId)?.focus();
          }}
        >
          <Icon name="plus" size={16} />
          {t("statistics:admin.new")}
        </Button>
      }
    >
      {list.isPending ? <FunctionalState state="loading" /> : null}
      <AdminSection title={t("statistics:admin.list")} icon="chart" flush>
        {domains.length > 1 ? (
          <div className="admin-pad">
            <AdminTabs
              label={t("statistics:admin.list")}
              current={domain}
              onChange={setDomain}
              tabs={[
                { key: "all", label: t("statistics:admin.all"), count: rows.length },
                ...domains.map((d) => ({
                  key: d,
                  label: d,
                  count: rows.filter((r) => r.key.startsWith(`${d}.`)).length,
                })),
              ]}
            />
          </div>
        ) : null}
        <AdminTable<Row>
          label={t("statistics:admin.list")}
          rows={shown}
          rowKey={(row) => row.key}
          columns={[
            {
              key: "key",
              header: t("statistics:admin.key"),
              primary: true,
              render: (row) => <code>{row.key}</code>,
            },
            {
              key: "status",
              header: t("statistics:admin.status"),
              render: (row) => (
                <StatusBadge tone={row.status === "active" ? "ok" : "neutral"}>{row.status}</StatusBadge>
              ),
            },
            {
              key: "version",
              header: t("statistics:admin.version"),
              render: (row) => `${row.active_version ?? "—"} / ${row.latest_version}`,
            },
          ]}
          actions={(row) => (
            <>
              <Button variant="ghost" onClick={() => setDraft(JSON.stringify(row.definition, null, 2))}>
                {t("statistics:admin.edit")}
                <span className="visually-hidden"> {row.key}</span>
              </Button>
              <Button variant="secondary" onClick={() => void confirmed("activate", row.key)}>
                {t("statistics:admin.activate")}
              </Button>
              <Button
                variant="ghost"
                disabled={row.status !== "active"}
                onClick={() => void confirmed("rebuild", row.key)}
              >
                {t("statistics:admin.rebuild")}
              </Button>
            </>
          )}
        />
      </AdminSection>
      <AdminSection title={t("statistics:admin.definition")} icon="settings">
        <JsonField
          id={editorId}
          label={t("statistics:admin.definition")}
          value={draft}
          onChange={setDraft}
          rows={14}
        />
        {errors.length ? (
          <ul role="alert" className="admin-errors">
            {errors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
        ) : null}
        <FormActions>
          <Button disabled={!draft.trim() || save.isPending} onClick={() => save.mutate()}>
            {t("statistics:admin.save")}
          </Button>
        </FormActions>
      </AdminSection>
    </AdminPage>
  );
}

const NEW_DEFINITION = `{
  "key": "domain.my_statistic",
  "version": 1
}`;

export default DefinitionsAdmin;
