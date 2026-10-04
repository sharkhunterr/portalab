import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { api } from "../../../api/client";
import { useAnnounce } from "../../../design-system/a11y/Announce";
import { Button } from "../../../design-system/components/Button";
import { PageHeader } from "../../../design-system/components/PageHeader";
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
  const headingId = useId();
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
  return (
    <section aria-labelledby={headingId}>
      <PageHeader titleId={headingId} level={2} icon="chart" title={t("statistics:admin.title")} />
      {list.isPending ? <FunctionalState state="loading" /> : null}
      <table>
        <thead>
          <tr>
            <th scope="col">{t("statistics:admin.key")}</th>
            <th scope="col">{t("statistics:admin.status")}</th>
            <th scope="col">{t("statistics:admin.version")}</th>
            <th scope="col">{t("statistics:admin.actions")}</th>
          </tr>
        </thead>
        <tbody>
          {(list.data ?? []).map((row) => (
            <tr key={row.key}>
              <th scope="row">{row.key}</th>
              <td>{row.status}</td>
              <td>
                {row.active_version ?? "—"} / {row.latest_version}
              </td>
              <td className="ds-stack ds-stack--row">
                <Button variant="secondary" onClick={() => setDraft(JSON.stringify(row.definition, null, 2))}>
                  {t("statistics:admin.edit")}
                </Button>
                <Button variant="secondary" onClick={() => void confirmed("activate", row.key)}>
                  {t("statistics:admin.activate")}
                </Button>
                <Button
                  variant="danger"
                  disabled={row.status !== "active"}
                  onClick={() => void confirmed("rebuild", row.key)}
                >
                  {t("statistics:admin.rebuild")}
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <label htmlFor={editorId}>{t("statistics:admin.definition")}</label>
      <textarea
        id={editorId}
        rows={14}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        spellCheck={false}
      />
      {errors.length ? (
        <ul role="alert">
          {errors.map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      ) : null}
      <Button disabled={!draft.trim() || save.isPending} onClick={() => save.mutate()}>
        {t("statistics:admin.save")}
      </Button>
    </section>
  );
}

export default DefinitionsAdmin;
