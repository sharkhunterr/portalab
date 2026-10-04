import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useMemo, useState } from "react";
import { api } from "../../api/client";
import {
  AdminPage,
  AdminSection,
  AdminTable,
  AdminTabs,
  AdminToolbar,
  FormActions,
  SearchBox,
  StatusBadge,
} from "../../design-system/admin/AdminKit";
import { Button } from "../../design-system/components/Button";
import { Dialog } from "../../design-system/components/Overlays";
import { useT } from "../../i18n/hooks/useT";
import { ApiError, DataRegion } from "../../state/regions";
import { Toggles } from "./Toggles";

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

/**
 * Configuration (spec 020 US5, 027 administration kit): settings grouped by area (tabs with counts) and
 * searchable, one table row per setting with its current value and where it comes from; "Modify" opens an
 * editor that previews the change before applying it. Sensitive values are write-only. Extensions can be
 * enabled or disabled below (data is never deleted).
 */
function parse(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

function display(value: unknown): string {
  if (typeof value === "string") return value === "" ? "—" : value;
  return JSON.stringify(value);
}

function area(key: string): string {
  return key.split(".")[0] ?? key;
}

function SettingEditor({ item }: { item: SettingItem }) {
  const t = useT();
  const fieldId = useId();
  const queryClient = useQueryClient();
  const [raw, setRaw] = useState(
    item.sensitive ? "" : typeof item.value === "string" ? item.value : JSON.stringify(item.value),
  );
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
    <form onSubmit={submit} className="config-editor">
      <p className="admin-muted">{item.description}</p>
      <div className="ds-field">
        <label htmlFor={fieldId}>{t("admin:config.newValue", { key: item.key })}</label>
        <input
          id={fieldId}
          value={raw}
          type={item.sensitive ? "password" : "text"}
          autoComplete="off"
          onChange={(event) => {
            setRaw(event.target.value);
            setPreview(null);
          }}
        />
        <span className="ds-field__hint">{t("admin:config.jsonHint")}</span>
      </div>
      {preview ? (
        <div role="status" className="config-editor__preview">
          {preview.ok ? (
            <>
              <p>
                {t("admin:config.before")} <code>{display(preview.diff[0]?.before)}</code> →{" "}
                {t("admin:config.after")} <code>{display(preview.diff[0]?.after)}</code>
              </p>
              {preview.warnings.map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
            </>
          ) : (
            <p role="alert">{preview.errors[0]?.detail ?? t("admin:config.invalid")}</p>
          )}
        </div>
      ) : null}
      {apply.isError ? (
        <p role="alert">{apply.error instanceof ApiError ? apply.error.message : t("admin:config.failed")}</p>
      ) : null}
      {apply.isSuccess ? <p role="status">{t("admin:config.applied")}</p> : null}
      <FormActions>
        <Button type="submit" variant="secondary">
          {t("admin:config.preview")}
        </Button>
        {preview?.ok ? (
          <Button type="button" onClick={() => apply.mutate()} disabled={apply.isPending}>
            {t("admin:config.apply")}
          </Button>
        ) : null}
      </FormActions>
    </form>
  );
}

export function ConfigEditor() {
  const t = useT();
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState("all");
  return (
    <DataRegion<SettingItem[]>
      label={t("admin:config.settings")}
      queryKey={["admin", "config"]}
      queryFn={async () =>
        ((await api.GET("/api/v1/admin/config")).data as unknown as { settings: SettingItem[] }).settings
      }
    >
      {(settings) => (
        <SettingsTable settings={settings} query={query} setQuery={setQuery} tab={tab} setTab={setTab} />
      )}
    </DataRegion>
  );
}

function SettingsTable({
  settings,
  query,
  setQuery,
  tab,
  setTab,
}: {
  settings: SettingItem[];
  query: string;
  setQuery: (value: string) => void;
  tab: string;
  setTab: (value: string) => void;
}) {
  const t = useT();
  const areas = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of settings) counts.set(area(item.key), (counts.get(area(item.key)) ?? 0) + 1);
    return [...counts.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [settings]);
  const needle = query.trim().toLowerCase();
  const shown = settings.filter(
    (item) =>
      (tab === "all" || area(item.key) === tab) &&
      (!needle || item.key.toLowerCase().includes(needle) || item.description.toLowerCase().includes(needle)),
  );
  return (
    <AdminSection title={t("admin:config.settings")} icon="settings" flush>
      <div className="config-toolbar">
        <AdminToolbar>
          <SearchBox label={t("admin:config.search")} value={query} onChange={setQuery} />
        </AdminToolbar>
        <AdminTabs
          label={t("admin:config.areas")}
          current={tab}
          onChange={setTab}
          tabs={[
            { key: "all", label: t("admin:config.all"), count: settings.length },
            ...areas.map(([key, count]) => ({ key, label: key, count })),
          ]}
        />
      </div>
      <AdminTable<SettingItem>
        label={t("admin:config.settings")}
        rows={shown}
        rowKey={(item) => item.key}
        empty={<p className="admin-muted config-empty">{t("admin:config.none")}</p>}
        columns={[
          {
            key: "key",
            header: t("admin:config.setting"),
            primary: true,
            render: (item) => (
              <span className="config-setting">
                <code>{item.key}</code>
                <span className="admin-muted">{item.description}</span>
              </span>
            ),
          },
          {
            key: "value",
            header: t("admin:config.value"),
            render: (item) =>
              item.sensitive ? (
                <span className="admin-muted">{t("admin:config.sensitive")}</span>
              ) : (
                <code className="config-value">{display(item.value)}</code>
              ),
          },
          {
            key: "source",
            header: t("admin:config.source"),
            render: (item) => (
              <StatusBadge tone={item.source === "default" ? "neutral" : "info"}>
                {t(`admin:config.sources.${item.source}`)}
              </StatusBadge>
            ),
          },
        ]}
        actions={(item) => (
          <Dialog
            title={item.key}
            closeLabel={t("admin:services.close")}
            trigger={
              <Button variant="ghost" aria-label={`${t("admin:config.modify")} ${item.key}`}>
                {t("admin:config.modify")}
              </Button>
            }
          >
            <SettingEditor item={item} />
          </Dialog>
        )}
      />
    </AdminSection>
  );
}

/** The routed Configuration page: settings, then extensions on/off. */
export function ConfigurationPage() {
  const t = useT();
  return (
    <AdminPage icon="settings" title={t("admin:config.title")} description={t("admin:config.subtitle")}>
      <ConfigEditor />
      <Toggles />
    </AdminPage>
  );
}
