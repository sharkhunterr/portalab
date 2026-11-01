import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, type ReactNode, useId, useMemo, useState } from "react";
import { api } from "../../api/client";
import { AdminPage, SearchBox, StatusBadge } from "../../design-system/admin/AdminKit";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { ApiError, DataRegion } from "../../state/regions";
import { EMAIL_KEYS, EmailSettings, SMTP_PASSWORD } from "./communication/EmailSettings";
import META from "./settings-meta.json";
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
  /** where it may be set: ``global`` (the portal), ``user`` (each member's own preference)… */
  scopes?: string[];
  /** each member sets their own: the portal's value is only their default */
  user_overridable?: boolean;
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

/**
 * Issue 14: the settings by what the administrator wants to do, not by module — each with a human title and
 * a sentence (``admin:setting.<key>.label|hint``); the ones rarely touched (timeouts, caches, raw structures)
 * and the technical keys only in the advanced mode.
 */
export const GROUPS = [
  ["general", "settings"],
  ["members", "users"],
  ["services", "server"],
  ["media", "film"],
  ["communication", "mail"],
  ["engagement", "trophy"],
  ["ai", "bot"],
  ["security", "shield"],
] as const;
type Group = (typeof GROUPS)[number][0];
const meta = META as Record<string, { group: Group; advanced: boolean }>;

export function groupOf(key: string): Group {
  return meta[key]?.group ?? "general";
}

/** Rarely touched — and a setting no title was written for yet. */
export function isAdvanced(key: string): boolean {
  return meta[key]?.advanced ?? true;
}

/** A setting's title, sentence and choices in the administrator's language (its description otherwise). */
export function useSettingText() {
  const t = useT();
  return useMemo(() => {
    const read = (id: string, fallback: string) => {
      const text = t(`admin:${id}`);
      return text === id ? fallback : text;
    };
    return {
      label: (item: Pick<SettingItem, "key" | "description">) =>
        read(`setting.${item.key}.label`, item.description || item.key),
      hint: (item: Pick<SettingItem, "key">) => read(`setting.${item.key}.hint`, ""),
      choice: (key: string, value: unknown) => read(`setting.${key}.choice.${String(value)}`, String(value)),
    };
  }, [t]);
}

const ADVANCED_KEY = "portalab.admin.settings.advanced";

function useAdvancedMode(): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState(() => {
    try {
      return window.localStorage.getItem(ADVANCED_KEY) === "1";
    } catch {
      return false;
    }
  });
  return [
    on,
    (next: boolean) => {
      setOn(next);
      try {
        window.localStorage.setItem(ADVANCED_KEY, next ? "1" : "0");
      } catch {
        // storage unavailable: the mode lasts for the page
      }
    },
  ];
}

/** Issue 319: the e-mail transport is set in one form (in « Communication »), not setting by setting. */
const TRANSPORT = new Set<string>([...Object.values(EMAIL_KEYS), SMTP_PASSWORD]);

export type { SettingItem };

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

/** One setting, edited in place with the control its type calls for — its title and sentence in the
 * administrator's language, its technical key in the advanced mode only. */
export function SettingCard({ item, advanced = false }: { item: SettingItem; advanced?: boolean }) {
  const t = useT();
  const text = useSettingText();
  const fieldId = useId();
  const { mutation, message, clear } = useApply(item);
  const initial =
    item.sensitive || item.value === null || item.value === undefined
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
            {text.choice(item.key, choice)}
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
          {text.label(item)}
        </label>
        {text.hint(item) ? <span className="setting-card__hint">{text.hint(item)}</span> : null}
        {advanced ? <code className="setting-card__key">{item.key}</code> : null}
        {item.source !== "default" && !item.sensitive && item.default !== undefined ? (
          <span className="setting-card__default">
            {t("admin:config.defaultIs", {
              value:
                item.choices?.length && typeof item.default !== "object"
                  ? text.choice(item.key, item.default)
                  : display(item.default),
            })}
          </span>
        ) : null}
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

export function useSettings() {
  return useQuery({
    queryKey: ["admin", "config"],
    queryFn: async () =>
      ((await api.GET("/api/v1/admin/config")).data as unknown as { settings: SettingItem[] }).settings,
  });
}

export function ConfigEditor() {
  const t = useT();
  const [query, setQuery] = useState("");
  // issue 321: the area asked in the address (« ?area=communication » from Newsletters & e-mail)
  const [tab, setTab] = useState<string>(() => {
    const asked = new URLSearchParams(window.location.search).get("area");
    return GROUPS.some(([key]) => key === asked) ? (asked as string) : "general";
  });
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
  const text = useSettingText();
  const [advanced, setAdvanced] = useAdvancedMode();
  // the portal's settings: a member's own preferences are set by each member, in « My settings »
  const portal = useMemo(
    () => settings.filter((item) => !item.scopes || item.scopes.includes("global")),
    [settings],
  );
  // a member's own preference (the portal's value only their default) is for the advanced mode too
  const visible = portal.filter(
    (item) => advanced || (!isAdvanced(item.key) && !item.user_overridable && !TRANSPORT.has(item.key)),
  );
  const counts = useMemo(() => {
    const out = new Map<string, number>();
    for (const item of visible) out.set(groupOf(item.key), (out.get(groupOf(item.key)) ?? 0) + 1);
    return out;
  }, [visible]);
  const needle = query.trim().toLowerCase();
  const found = (item: SettingItem) =>
    [text.label(item), text.hint(item), item.description, advanced ? item.key : ""]
      .join(" ")
      .toLowerCase()
      .includes(needle);
  const shown = visible.filter((item) => (needle ? found(item) : tab === "all" || groupOf(item.key) === tab));
  const changed = portal.filter((s) => s.source !== "default").length;
  return (
    <div className="settings-explorer">
      <nav className="settings-explorer__areas" aria-label={t("admin:config.areas")}>
        <SearchBox label={t("admin:config.search")} value={query} onChange={setQuery} />
        <ul>
          {GROUPS.map(([key, icon]) => (
            <li key={key}>
              <button type="button" aria-pressed={!needle && tab === key} onClick={() => setTab(key)}>
                <Icon name={icon} size={16} />
                <span>{t(`admin:config.group.${key}`)}</span>
                <span className="settings-explorer__count">{counts.get(key) ?? 0}</span>
              </button>
            </li>
          ))}
          <li>
            <button type="button" aria-pressed={!needle && tab === "all"} onClick={() => setTab("all")}>
              <Icon name="list" size={16} />
              <span>{t("admin:config.all")}</span>
              <span className="settings-explorer__count">{visible.length}</span>
            </button>
          </li>
        </ul>
        <label className="settings-explorer__advanced">
          <input type="checkbox" checked={advanced} onChange={(event) => setAdvanced(event.target.checked)} />
          <span>{t("admin:config.advanced")}</span>
        </label>
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
              : t(`admin:config.group.${tab}`)}
        </h2>
        {!needle && tab !== "all" ? (
          <p className="admin-muted settings-explorer__lead">{t(`admin:config.groupHint.${tab}`)}</p>
        ) : null}
        {!needle && tab === "communication" && !advanced ? <EmailSettings /> : null}
        {shown.length ? (
          <ul className="setting-cards">
            {shown.map((item) => (
              <SettingCard
                key={`${item.key}:${JSON.stringify(item.value)}`}
                item={item}
                advanced={advanced}
              />
            ))}
          </ul>
        ) : (
          <p className="admin-muted config-empty">
            {advanced ? t("admin:config.none") : t("admin:config.noneSimple")}
          </p>
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
