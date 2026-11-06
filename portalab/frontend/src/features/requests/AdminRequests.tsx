import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { AdminSection, FormActions, FormGrid } from "../../design-system/admin/AdminKit";
import { Button } from "../../design-system/components/Button";
import { CheckboxField } from "../../design-system/components/Field";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useT } from "../../i18n/hooks/useT";
import { type AskConfig, useAskOptions, useSaveAskConfig } from "./api";
import "../admin/admin.css";

/**
 * Issue 363, issue 378: the kinds of titles members ask the team for (books, audiobooks, games…) — a tab of
 * the media's « Requests » page. Their requests are in its queue with the films' and series'; quotas and
 * rewards are those of every request.
 */
function useKindsSetting() {
  return useQuery({
    queryKey: ["requests", "config"],
    retry: false,
    queryFn: async () => {
      const settings = (
        (await api.GET("/api/v1/admin/config")).data as unknown as {
          settings: { key: string; value: unknown }[];
        }
      ).settings;
      return (settings.find((s) => s.key === "requests.config")?.value ?? null) as AskConfig | null;
    },
  });
}

/** Whether the team takes requests (the module switched on: its setting declared). */
export function useTitleRequestsOn(): boolean {
  return Boolean(useKindsSetting().data);
}

export function TitleRequestKinds() {
  const t = useT();
  const current = useKindsSetting();
  const options = useAskOptions();
  const save = useSaveAskConfig();
  const [kinds, setKinds] = useState<string[] | null>(null);
  useEffect(() => {
    if (current.data && kinds === null) setKinds(current.data.kinds);
  }, [current.data, kinds]);
  if (!current.data || kinds === null) return <FunctionalState state="loading" />;
  return (
    <AdminSection title={t("media:ask.admin.settings")} description={t("media:ask.admin.settingsHint")}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate({ kinds });
        }}
      >
        <FormGrid>
          {(options.data?.known ?? []).map((kind) => (
            <CheckboxField
              key={kind}
              label={t(`media:kind.${kind}`)}
              checked={kinds.includes(kind)}
              onChange={(e) =>
                setKinds(e.target.checked ? [...kinds, kind] : kinds.filter((k) => k !== kind))
              }
            />
          ))}
        </FormGrid>
        <FormActions>
          <Button type="submit" disabled={save.isPending}>
            {t("media:ask.admin.save")}
          </Button>
        </FormActions>
        {save.isSuccess ? <p role="status">{t("media:ask.admin.saved")}</p> : null}
        {save.isError ? <p role="alert">{t("media:ask.error.failed")}</p> : null}
      </form>
    </AdminSection>
  );
}
