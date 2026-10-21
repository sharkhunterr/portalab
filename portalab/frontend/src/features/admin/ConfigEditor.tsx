import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, type ReactNode, useId, useMemo, useState } from "react";
import { api } from "../../api/client";
import { AdminPage, SearchBox, StatusBadge } from "../../design-system/admin/AdminKit";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { ApiError, DataRegion } from "../../state/regions";
import { Toggles } from "./Toggles";

interface SettingItem {
  key: string;
  description: string;
  sensitive: boolean;
  value: unknown;
  source: string;
  default?: unknown;
  /** 027: how it is edited — boolean, integer, number, string or json — and the allowed values. */
  kind?: "boolean" | "integer" | "number" | "string" | "json";
  choices?: unknown[];
}

interface PreviewResult {
  ok: boolean;
  diff: { key: string; before: unknown; after: unknown }[];
  warnings: string[];
  errors: { key: string; detail: string }[];
}

/**
 * Configuration (spec 020 US5; 027 redesign): every setting of the portal, grouped by area in a side list
 * and searchable; each setting is a card — what it does, where its value comes from — edited in place with
 * the right control (a switch, a number, a list of choices, text or JSON). Saving validates first (the
 * server checks the value and reports what changes), then applies; « reset » goes back to the default.
 * Sensitive values are write-only.
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

const AREA_ICONS: Record<string, string> = {
  admin: "shield",
  ai: "bot",
  authz: "key",
  automations: "zap",
  calendar: "calendar",
  campaigns: "star",
  community: "users",
  connectors: "plug",
  content: "newspaper",
  dashboard: "dashboard",
  events: "activity",
  gamification: "trophy",
  health: "activity",
  i18n: "globe",
  identity: "user",
  marketplace: "shop",
  media: "film",
  news: "newspaper",
  notifications: "bell",
  observability: "gauge",
  plugins: "plug",
  privacy: "lock",
  search: "search",
  statistics: "chart",
  support: "lifebuoy",
  ui: "palette",
  wiki: "book",
};

function useApply(item: SettingItem) {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const t = useT();
  const mutation = useMutation({
    mutationFn: async (change: { value?: unknown; unset?: boolean }) => {
      const body = {
        changes: [
          {
            key: item.key,
            value: change.unset ? null : change.value,
            scope: "global" as const,
            scope_ref: "",
            unset: Boolean(change.unset),
          },
        ],
        reason: "",
      };
      const preview = (await api.POST("/api/v1/admin/config/validate", { body })).data as unknown as
        | PreviewResult
        | undefined;
      if (preview && !preview.ok) throw new Error(preview.errors[0]?.detail ?? t("admin:config.invalid"));
      await api.PUT("/api/v1/admin/config", { body });
      return preview;
    },
    onSuccess: (preview) => {
      const diff = preview?.diff[0];
      setMessage({
        ok: true,
        text:
          diff && !item.sensitive
            ? `${t("admin:config.applied")} (${display(diff.before)} → ${display(diff.after)})`
            : t("admin:config.applied"),
      });
      void queryClient.invalidateQueries({ queryKey: ["admin", "config"] });
    },
    onError: (error) =>
      setMessage({
        ok: false,
        text: error instanceof ApiError || error instanceof Error ? error.message : t("admin:config.failed"),
      }),
  });
  return { mutation, message, clear: () => setMessage(null) };
}

/** One setting, edited in place with the control its type calls for. */
function SettingCard({ item }: { item: SettingItem }) {
  const t = useT();
  const fieldId = useId();
  const { mutation, message, clear } = useApply(item);
  const initial = item.sensitive
    ? ""
    : typeof item.value === "string"
      ? item.value
      : JSON.stringify(item.value);
  const [raw, setRaw] = useState(initial);
  const kind = item.kind ?? "json";
  const dirty = raw !== initial;
  const save = (value: unknown) => mutation.mutate({ value });
  const typed = () =>
    kind === "integer" || kind === "number" ? Number(raw) : kind === "string" ? raw : parse(raw);
  let control: ReactNode;
  if (kind === "boolean" && !item.sensitive) {
    control = (
      <span className="setting-switch">
        <input
          id={fieldId}
          type="checkbox"
          role="switch"
          aria-checked={Boolean(item.value)}
          checked={Boolean(item.value)}
          disabled={mutation.isPending}
          onChange={(event) => save(event.target.checked)}
        />
        <span aria-hidden="true">{item.value ? t("admin:config.on") : t("admin:config.off")}</span>
      </span>
    );
  } else if (item.choices?.length && !item.sensitive) {
    control = (
      <select
        id={fieldId}
        className="setting-input"
        value={String(item.value)}
        disabled={mutation.isPending}
        onChange={(event) => save(event.target.value)}
      >
        {item.choices.map((choice) => (
          <option key={String(choice)} value={String(choice)}>
            {String(choice)}
          </option>
        ))}
      </select>
    );
  } else {
    const multiline = kind === "json" && !item.sensitive;
    control = (
      <form
        className="setting-edit"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          save(item.sensitive ? raw : typed());
        }}
      >
        {multiline ? (
          <textarea
            id={fieldId}
            className="setting-input setting-input--json"
            rows={Math.min(8, Math.max(2, raw.split("\n").length))}
            value={raw}
            onChange={(event) => {
              setRaw(event.target.value);
              clear();
            }}
          />
        ) : (
          <input
            id={fieldId}
            className="setting-input"
            type={item.sensitive ? "password" : kind === "integer" || kind === "number" ? "number" : "text"}
            step={kind === "number" ? "any" : undefined}
            autoComplete="off"
            placeholder={item.sensitive ? t("admin:config.sensitive") : undefined}
            value={raw}
            onChange={(event) => {
              setRaw(event.target.value);
              clear();
            }}
          />
        )}
        {dirty ? (
          <Button type="submit" disabled={mutation.isPending}>
            <Icon name="check" size={14} />
            {t("admin:config.save")}
          </Button>
        ) : null}
      </form>
    );
  }
  return (
    <li className="setting-card" data-changed={item.source !== "default" || undefined}>
      <div className="setting-card__text">
        <label htmlFor={fieldId} className="setting-card__label">
          {item.description || item.key}
        </label>
        <code className="setting-card__key">{item.key}</code>
      </div>
      <div className="setting-card__control">
        {control}
        {item.sensitive && item.source !== "default" ? (
          <span className="admin-muted">{t("admin:config.sensitive")}</span>
        ) : null}
      </div>
      <div className="setting-card__meta">
        <StatusBadge tone={item.source === "default" ? "neutral" : "info"}>
          {t(`admin:config.sources.${item.source}`)}
        </StatusBadge>
        {item.source !== "default" ? (
          <Button
            variant="ghost"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate({ unset: true })}
            title={t("admin:config.resetHint")}
          >
            <Icon name="sync" size={14} />
            {t("admin:config.reset")}
          </Button>
        ) : null}
      </div>
      {message ? (
        <p
          role={message.ok ? "status" : "alert"}
          className="setting-card__message"
          data-ok={message.ok || undefined}
        >
          {message.text}
        </p>
      ) : null}
    </li>
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
        <SettingsExplorer settings={settings} query={query} setQuery={setQuery} tab={tab} setTab={setTab} />
      )}
    </DataRegion>
  );
}

function SettingsExplorer({
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
      (tab === "all" || needle || area(item.key) === tab) &&
      (!needle || item.key.toLowerCase().includes(needle) || item.description.toLowerCase().includes(needle)),
  );
  const changed = settings.filter((s) => s.source !== "default").length;
  const label = (key: string) => {
    const text = t(`admin:config.area.${key}`);
    return text === `config.area.${key}` ? key.charAt(0).toUpperCase() + key.slice(1) : text;
  };
  return (
    <div className="settings-explorer">
      <nav className="settings-explorer__areas" aria-label={t("admin:config.areas")}>
        <SearchBox label={t("admin:config.search")} value={query} onChange={setQuery} />
        <ul>
          {[["all", settings.length] as const, ...areas].map(([key, count]) => (
            <li key={key}>
              <button type="button" aria-pressed={!needle && tab === key} onClick={() => setTab(key)}>
                <Icon name={key === "all" ? "list" : (AREA_ICONS[key] ?? "settings")} size={16} />
                <span>{key === "all" ? t("admin:config.all") : label(key)}</span>
                <span className="settings-explorer__count">{count}</span>
              </button>
            </li>
          ))}
        </ul>
        <p className="admin-muted settings-explorer__changed">
          {t("admin:config.changed", { count: changed })}
        </p>
      </nav>
      <div className="settings-explorer__list">
        <h2 className="settings-explorer__title">
          {needle
            ? t("admin:config.results", { count: shown.length })
            : tab === "all"
              ? t("admin:config.all")
              : label(tab)}
        </h2>
        {shown.length ? (
          <ul className="setting-cards">
            {shown.map((item) => (
              <SettingCard key={`${item.key}:${JSON.stringify(item.value)}`} item={item} />
            ))}
          </ul>
        ) : (
          <p className="admin-muted config-empty">{t("admin:config.none")}</p>
        )}
      </div>
    </div>
  );
}

/**
 * The routed Configuration page (« System »): every setting, then extensions on/off — the e-mail transport
 * moved to « Newsletters & e-mail » (admin reorganisation, trial).
 */
export function ConfigurationPage() {
  const t = useT();
  return (
    <AdminPage icon="settings" title={t("admin:config.title")} description={t("admin:config.subtitle")}>
      <ConfigEditor />
      <Toggles />
    </AdminPage>
  );
}
