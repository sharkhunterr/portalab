import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, type ReactNode, useEffect, useId, useMemo, useRef, useState } from "react";
import { api } from "../../../api/client";
import { usePreferences } from "../../../design-system/a11y/PreferencesProvider";
import { AdminPage, AdminSection } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { Card } from "../../../design-system/components/Content";
import { SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog, DialogActions } from "../../../design-system/components/Overlays";
import { sound } from "../../../design-system/sound/SoundService";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { applyToDocument } from "../../../design-system/themes/apply";
import { DEFAULT_THEME_KEY } from "../../../design-system/themes/builtin";
import { floorReport } from "../../../design-system/themes/floor";
import {
  CARD_STYLES,
  CELEBRATIONS,
  COLOR_PICKER_FALLBACK,
  CONTENT_WIDTHS,
  CORNER_STYLES,
  HEADER_POSITIONS,
  HEADER_STYLES,
  MOTION_PROFILES,
  NAV_DESKTOP,
  NAV_PHONE,
  NAV_TABLET,
  parseTheme,
  presentationOf,
  RARITIES,
  SOUND_EVENTS,
  type ThemeDefinition,
  WIDGET_FRAMES,
} from "../../../design-system/themes/schema";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { withConfirmation } from "../../marketplace/admin/confirm";
import { appearanceStrings, ThemeMiniature } from "../AppearanceSettings";
import "./studio.css";

/**
 * Theme studio (027 US11, T096): every theme with its miniature, source, accessibility verdict and whether
 * members are offered it or must buy it. "Duplicate" opens a visual editor — identity, colors, layout
 * (menu per device, header position, cards…), motion and sounds — with a live preview of the draft and the
 * accessibility floor computed as you type (the server runs the same rules on save). A saved theme is
 * offered to members in one click, or sold in the shop: the product is created, published and the theme
 * becomes reserved to its buyers.
 */
interface AdminTheme {
  key: string;
  name: string;
  definition: ThemeDefinition;
  source: string;
  enabled: boolean;
  floor_ok: boolean | null;
}

interface ShopProduct {
  key: string;
  type: string;
  state: string;
  theme?: string | null;
}

const THEMES_KEY = ["admin", "ui", "themes"] as const;
const POLICY_KEY = ["admin", "ui", "policy"] as const;
const FONTS = [
  "",
  "Inter, system-ui, sans-serif",
  "system-ui, sans-serif",
  "Georgia, serif",
  '"Trebuchet MS", sans-serif',
  "ui-monospace, monospace",
];
/** Bundled sounds (``public/assets/sounds``) a theme may use for any event. */
const SOUND_NAMES: Record<string, string> = {
  "asset:portalab/notification.wav": "notification",
  "asset:portalab/alert.wav": "alert",
  "asset:portalab/success.wav": "success",
  "asset:portalab/reward.wav": "reward",
  "asset:portalab/level-up.wav": "levelUp",
  "asset:portalab/ui.wav": "ui",
};
const SOUND_ASSETS = Object.keys(SOUND_NAMES);
const COLOR_ROLES = [
  "surface",
  "surfaceRaised",
  "text",
  "textMuted",
  "border",
  "accent",
  "accentContrast",
  "focus",
  "accentAlt",
] as const;
type ColorRole = (typeof COLOR_ROLES)[number];

function slug(name: string): string {
  const base = name
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return /^[a-z]/.test(base) ? base.slice(0, 40) : `theme-${base}`.slice(0, 40);
}

function errorDetail(error: unknown): string {
  if (error instanceof ApiError) {
    const violations = error.extensions.violations;
    if (Array.isArray(violations) && violations.length) return violations.join(" · ");
    return error.message;
  }
  return String(error);
}

/** A copy that stands on its own: new key and name, no family (a family groups the portal's own themes). */
export function duplicate(theme: ThemeDefinition, name: string, taken: ReadonlySet<string>): ThemeDefinition {
  const { family: _family, ...rest } = structuredClone(theme);
  let key = slug(name);
  for (let n = 2; taken.has(key); n += 1) key = `${slug(name).slice(0, 36)}-${n}`;
  return { ...rest, schemaVersion: 2, key, name };
}

export default function ThemeStudio() {
  const t = useT();
  const client = useQueryClient();
  const themes = useQuery({
    queryKey: THEMES_KEY,
    queryFn: async () =>
      ((await api.GET("/api/v1/admin/ui/themes")).data as unknown as { items: AdminTheme[] }).items,
  });
  const policy = useQuery({
    queryKey: POLICY_KEY,
    queryFn: async () =>
      ((await api.GET("/api/v1/ui/themes")).data as unknown as { policy: { allowedThemes: string[] } })
        .policy,
  });
  const products = useQuery({
    queryKey: ["admin", "marketplace", "products", "themes"],
    retry: false,
    queryFn: async () =>
      ((await api.GET("/api/v1/admin/marketplace/products")).data as unknown as ShopProduct[]).filter(
        (product) => product.type === "theme",
      ),
  });
  const [editing, setEditing] = useState<{ draft: ThemeDefinition; existing: boolean } | null>(null);
  const [selling, setSelling] = useState<AdminTheme | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const allowed = new Set(policy.data?.allowedThemes ?? []);
  const sold = new Map(
    (products.data ?? []).filter((p) => p.theme && p.state === "available").map((p) => [p.theme, p.key]),
  );
  const taken = new Set((themes.data ?? []).map((theme) => theme.key));
  const refresh = () => {
    void client.invalidateQueries({ queryKey: ["admin", "ui"] });
    void client.invalidateQueries({ queryKey: ["ui", "themes"] });
    void client.invalidateQueries({ queryKey: ["admin", "marketplace"] });
  };
  const offer = useMutation({
    mutationFn: async ({ key, on }: { key: string; on: boolean }) => {
      const next = on ? [...allowed, key] : [...allowed].filter((k) => k !== key);
      await api.PUT("/api/v1/admin/config", {
        body: {
          changes: [
            {
              key: "ui.allowedThemes",
              value: [...new Set(next)],
              scope: "global",
              scope_ref: "",
              unset: false,
            },
          ],
          reason: "theme studio",
        },
      });
    },
    onSuccess: refresh,
    onError: (error) => setMessage(errorDetail(error)),
  });
  const toggle = useMutation({
    mutationFn: async ({ key, enabled }: { key: string; enabled: boolean }) =>
      api.PATCH("/api/v1/admin/ui/themes/{key}", { params: { path: { key } }, body: { enabled } }),
    onSuccess: refresh,
    onError: (error) => setMessage(errorDetail(error)),
  });
  const startFrom = (theme: ThemeDefinition) =>
    setEditing({
      draft: duplicate(theme, t("admin:studio.copyOf", { name: theme.name }), taken),
      existing: false,
    });
  const base = themes.data?.find((theme) => theme.key === DEFAULT_THEME_KEY)?.definition;
  return (
    <AdminPage
      icon="palette"
      title={t("admin:studio.title")}
      description={t("admin:studio.subtitle")}
      primary={
        base ? (
          <Button onClick={() => startFrom(base)}>
            <Icon name="plus" size={16} />
            {t("admin:studio.new")}
          </Button>
        ) : undefined
      }
    >
      {message ? (
        <p role="alert" className="theme-studio__alert">
          {message}
        </p>
      ) : null}
      {editing ? (
        <ThemeEditor
          key={editing.draft.key}
          initial={editing.draft}
          existing={editing.existing}
          onClose={() => setEditing(null)}
          onSaved={(key) => {
            refresh();
            setEditing(null);
            setMessage(null);
            if (!allowed.has(key)) offer.mutate({ key, on: true });
          }}
        />
      ) : null}
      {themes.isPending ? <FunctionalState state="loading" /> : null}
      {themes.isError ? <FunctionalState state="unauthorized" /> : null}
      <AdminSection title={t("admin:studio.themes")} icon="palette">
        <ul className="theme-studio__list" aria-label={t("admin:studio.themes")}>
          {(themes.data ?? []).map((theme) => {
            const parsed = parseTheme(theme.definition).theme;
            const forSale = sold.has(theme.key);
            return (
              <li key={theme.key} className="theme-studio__item" data-enabled={theme.enabled}>
                {parsed ? <ThemeMiniature theme={parsed} /> : null}
                <span className="theme-studio__name">
                  <strong>{theme.name}</strong>
                  <code>{theme.key}</code>
                </span>
                <span className="theme-studio__badges">
                  <span className="ds-badge">
                    {t(
                      theme.source === "builtin"
                        ? "admin:studio.source.builtin"
                        : theme.source === "admin"
                          ? "admin:studio.source.admin"
                          : "admin:studio.source.other",
                    )}
                  </span>
                  <span className="ds-badge" data-ok={theme.floor_ok !== false}>
                    {theme.floor_ok === false ? t("admin:studio.floorKo") : t("admin:studio.floorOk")}
                  </span>
                  {forSale ? (
                    <span className="ds-badge theme-studio__sold">
                      <Icon name="shop" size={12} />
                      {t("admin:studio.sold")}
                    </span>
                  ) : allowed.has(theme.key) ? (
                    <span className="ds-badge" data-ok="true">
                      {t("admin:studio.offered")}
                    </span>
                  ) : null}
                  {!theme.enabled ? <span className="ds-badge">{t("admin:studio.disabled")}</span> : null}
                </span>
                <span className="theme-studio__actions">
                  {parsed ? (
                    <Button variant="secondary" onClick={() => startFrom(parsed)}>
                      <Icon name="plus" size={16} />
                      {t("admin:studio.duplicate")}
                      <span className="visually-hidden">: {theme.name}</span>
                    </Button>
                  ) : null}
                  {parsed && theme.source === "admin" ? (
                    <Button variant="ghost" onClick={() => setEditing({ draft: parsed, existing: true })}>
                      <Icon name="settings" size={16} />
                      {t("admin:studio.edit")}
                      <span className="visually-hidden">: {theme.name}</span>
                    </Button>
                  ) : null}
                  {theme.source !== "builtin" ? (
                    <Button
                      variant="ghost"
                      onClick={() => toggle.mutate({ key: theme.key, enabled: !theme.enabled })}
                    >
                      {theme.enabled ? t("admin:studio.disable") : t("admin:studio.enable")}
                    </Button>
                  ) : null}
                  {theme.enabled && !forSale ? (
                    <Button
                      variant="ghost"
                      onClick={() => offer.mutate({ key: theme.key, on: !allowed.has(theme.key) })}
                    >
                      {allowed.has(theme.key) ? t("admin:studio.withdraw") : t("admin:studio.offer")}
                    </Button>
                  ) : null}
                  {theme.enabled && !forSale && theme.source !== "builtin" ? (
                    <Button variant="ghost" onClick={() => setSelling(theme)}>
                      <Icon name="shop" size={16} />
                      {t("admin:studio.sell")}
                    </Button>
                  ) : null}
                </span>
              </li>
            );
          })}
        </ul>
      </AdminSection>
      {selling ? (
        <SellDialog
          theme={selling}
          onClose={() => setSelling(null)}
          onDone={() => {
            if (!allowed.has(selling.key)) offer.mutate({ key: selling.key, on: true });
            refresh();
          }}
        />
      ) : null}
    </AdminPage>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="theme-studio__section">
      <legend>{title}</legend>
      <div className="theme-studio__fields">{children}</div>
    </fieldset>
  );
}

function Choice<T extends string>({
  label,
  value,
  options,
  labels,
  onChange,
}: {
  label: string;
  value: T;
  options: readonly T[];
  labels?: Record<string, string>;
  onChange: (value: T) => void;
}) {
  return (
    <SelectField label={label} value={value} onChange={(event) => onChange(event.target.value as T)}>
      {options.map((option) => (
        <option key={option} value={option}>
          {labels?.[option] ?? option}
        </option>
      ))}
    </SelectField>
  );
}

function ColorField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const id = useId();
  const hex = /^#[0-9a-f]{6}$/i.test(value) ? value : null;
  return (
    <div className="ds-field theme-studio__color">
      <label htmlFor={id}>{label}</label>
      <span>
        <input
          type="color"
          aria-label={label}
          value={hex ?? COLOR_PICKER_FALLBACK}
          onChange={(event) => onChange(event.target.value)}
        />
        <input id={id} value={value} spellCheck={false} onChange={(event) => onChange(event.target.value)} />
      </span>
    </div>
  );
}

function ThemeEditor({
  initial,
  existing,
  onClose,
  onSaved,
}: {
  initial: ThemeDefinition;
  existing: boolean;
  onClose: () => void;
  onSaved: (key: string) => void;
}) {
  const t = useT();
  const [draft, setDraft] = useState<ThemeDefinition>(initial);
  const [error, setError] = useState<string | null>(null);
  const p = presentationOf(draft);
  const parsed = useMemo(() => parseTheme(draft), [draft]);
  const floor = useMemo(() => (parsed.theme ? floorReport(parsed.theme) : null), [parsed]);
  const failing = floor?.checks.filter((check) => !check.ok) ?? [];
  const setColor = (role: ColorRole, value: string) =>
    setDraft((d) => ({ ...d, colors: { ...d.colors, [role]: value } }));
  const setLayout = (patch: Partial<NonNullable<ThemeDefinition["layout"]>>) =>
    setDraft((d) => ({ ...d, layout: { ...d.layout, ...patch } }));
  const setNav = (device: "desktop" | "tablet" | "phone", value: string) =>
    setDraft((d) => ({
      ...d,
      layout: { ...d.layout, nav: { ...presentationOf(d).nav, ...d.layout?.nav, [device]: value } },
    }));
  const setMotion = (patch: Partial<NonNullable<ThemeDefinition["motion"]>>) =>
    setDraft((d) => ({ ...d, motion: { ...d.motion, ...patch } }));
  const save = useMutation({
    mutationFn: async () =>
      existing
        ? api.PATCH("/api/v1/admin/ui/themes/{key}", {
            params: { path: { key: draft.key } },
            body: { definition: draft as unknown as Record<string, never> },
          })
        : api.POST("/api/v1/admin/ui/themes", {
            body: { definition: draft as unknown as Record<string, never> },
          }),
    onSuccess: () => onSaved(draft.key),
    onError: (e) => setError(t("admin:studio.saveFailed", { detail: errorDetail(e) })),
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };
  const layouts = appearanceStrings.layouts;
  return (
    <Card
      className="theme-studio__editor"
      title={existing ? t("admin:studio.editor.edit", { name: initial.name }) : t("admin:studio.editor.new")}
      icon="palette"
      actions={
        <Button variant="ghost" size="icon" aria-label={t("admin:studio.editor.close")} onClick={onClose}>
          <Icon name="close" size={18} />
        </Button>
      }
    >
      <div className="theme-studio__workbench">
        <form onSubmit={submit} className="theme-studio__form">
          <Section title={t("admin:studio.section.identity")}>
            <TextField
              label={t("admin:studio.field.name")}
              value={draft.name}
              required
              maxLength={80}
              onChange={(event) => {
                const name = event.target.value;
                setDraft((d) => ({ ...d, name, ...(existing ? {} : { key: slug(name) || d.key }) }));
              }}
            />
            <TextField
              label={t("admin:studio.field.key")}
              hint={t("admin:studio.field.key.hint")}
              value={draft.key}
              disabled={existing}
              pattern="[a-z][a-z0-9-]{1,47}"
              onChange={(event) => setDraft((d) => ({ ...d, key: event.target.value }))}
            />
            <Choice
              label={t("admin:studio.field.scheme")}
              value={draft.colorScheme}
              options={["dark", "light"] as const}
              labels={{ dark: t("admin:studio.scheme.dark"), light: t("admin:studio.scheme.light") }}
              onChange={(colorScheme) => setDraft((d) => ({ ...d, colorScheme }))}
            />
          </Section>
          <Section title={t("admin:studio.section.colors")}>
            {COLOR_ROLES.map((role) => (
              <ColorField
                key={role}
                label={t(`admin:studio.color.${role}`)}
                value={draft.colors[role] ?? draft.colors.accent}
                onChange={(value) => setColor(role, value)}
              />
            ))}
          </Section>
          <Section title={t("admin:studio.section.layout")}>
            <Choice
              label={t("admin:studio.field.navDesktop")}
              value={p.nav.desktop}
              options={NAV_DESKTOP}
              labels={layouts}
              onChange={(v) => setNav("desktop", v)}
            />
            <Choice
              label={t("admin:studio.field.navTablet")}
              value={p.nav.tablet}
              options={NAV_TABLET}
              labels={layouts}
              onChange={(v) => setNav("tablet", v)}
            />
            <Choice
              label={t("admin:studio.field.navPhone")}
              value={p.nav.phone}
              options={NAV_PHONE}
              labels={layouts}
              onChange={(v) => setNav("phone", v)}
            />
            <Choice
              label={t("admin:studio.field.headerPosition")}
              value={p.headerPosition}
              options={HEADER_POSITIONS}
              onChange={(headerPosition) => setLayout({ headerPosition })}
            />
            <Choice
              label={t("admin:studio.field.header")}
              value={p.header}
              options={HEADER_STYLES}
              onChange={(header) => setLayout({ header })}
            />
            <Choice
              label={t("admin:studio.field.cards")}
              value={p.cards}
              options={CARD_STYLES}
              onChange={(cards) => setLayout({ cards })}
            />
            <Choice
              label={t("admin:studio.field.content")}
              value={p.content}
              options={CONTENT_WIDTHS}
              onChange={(content) => setLayout({ content })}
            />
            <Choice
              label={t("admin:studio.field.corners")}
              value={p.corners}
              options={CORNER_STYLES}
              onChange={(corners) => setLayout({ corners })}
            />
            <Choice
              label={t("admin:studio.field.widgetFrame")}
              value={p.widgetFrame}
              options={WIDGET_FRAMES}
              onChange={(widgetFrame) => setLayout({ widgetFrame })}
            />
          </Section>
          <Section title={t("admin:studio.section.motion")}>
            <Choice
              label={t("admin:studio.field.motion")}
              value={p.motion}
              options={MOTION_PROFILES}
              onChange={(profile) => setMotion({ profile })}
            />
            <Choice
              label={t("admin:studio.field.celebration")}
              value={p.celebration}
              options={CELEBRATIONS}
              onChange={(celebration) => setMotion({ celebration })}
            />
            <SelectField
              label={t("admin:studio.field.font")}
              value={draft.typography?.fontFamily ?? ""}
              onChange={(event) => {
                const fontFamily = event.target.value;
                setDraft((d) => {
                  const { fontFamily: _old, ...typography } = d.typography ?? {};
                  return { ...d, typography: fontFamily ? { ...typography, fontFamily } : typography };
                });
              }}
            >
              {FONTS.map((font) => (
                <option key={font} value={font}>
                  {font ? font.split(",")[0]?.replace(/"/g, "") : "—"}
                </option>
              ))}
            </SelectField>
          </Section>
          <Section title={t("admin:studio.section.sounds")}>
            {SOUND_EVENTS.map((event) => (
              <SoundField
                key={event}
                event={event}
                value={draft.sounds?.[event] ?? ""}
                onChange={(asset) =>
                  setDraft((d) => {
                    const { [event]: _old, ...sounds } = d.sounds ?? {};
                    return { ...d, sounds: asset ? { ...sounds, [event]: asset } : sounds };
                  })
                }
              />
            ))}
          </Section>
          {error ? <p role="alert">{error}</p> : null}
          <div className="theme-studio__save">
            <Button type="submit" disabled={save.isPending || failing.length > 0 || !parsed.theme}>
              <Icon name="check" size={16} />
              {t("admin:studio.save")}
            </Button>
          </div>
        </form>
        <aside className="theme-studio__side" aria-label={t("admin:studio.preview")}>
          <p className="theme-studio__label">{t("admin:studio.preview")}</p>
          <Preview theme={draft} />
          <section className="theme-studio__floor" aria-label={t("admin:studio.floor")}>
            <p className="theme-studio__label">{t("admin:studio.floor")}</p>
            {parsed.errors.length ? (
              <ul className="theme-studio__errors">
                {parsed.errors.slice(0, 5).map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
            ) : failing.length ? (
              <>
                <p role="status" data-ok="false">
                  {t("admin:studio.floor.ko", { count: failing.length })}
                </p>
                <ul className="theme-studio__errors">
                  {failing.slice(0, 6).map((check) => (
                    <li key={check.pair}>
                      {check.pair}: {check.ratio} / {check.minimum}
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <p role="status" data-ok="true">
                <Icon name="check" size={16} />
                {t("admin:studio.floor.ok")}
              </p>
            )}
          </section>
        </aside>
      </div>
    </Card>
  );
}

/** One theme sound: any bundled sound (or silence) for an event, with a button to listen to it. */
function SoundField({
  event,
  value,
  onChange,
}: {
  event: (typeof SOUND_EVENTS)[number];
  value: string;
  onChange: (asset: string) => void;
}) {
  const t = useT();
  const label = t(`admin:studio.sound.${event}`);
  const url = value ? sound.resolve(value) : null;
  return (
    <div className="theme-studio__sound">
      <SelectField label={label} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{t("admin:studio.sound.none")}</option>
        {SOUND_ASSETS.map((asset) => (
          <option key={asset} value={asset}>
            {t(`admin:studio.sound.${SOUND_NAMES[asset] ?? "ui"}`)}
          </option>
        ))}
      </SelectField>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        disabled={!url}
        aria-label={t("admin:studio.sound.play", { event: label })}
        onClick={() => {
          if (url) void new Audio(url).play().catch(() => undefined);
        }}
      >
        <Icon name="bell" size={16} />
      </Button>
    </div>
  );
}

/** The draft applied to a frame of its own (CSS variables + layout attributes): the portal is untouched. */
function Preview({ theme }: { theme: ThemeDefinition }) {
  const t = useT();
  const { preferences } = usePreferences();
  const frame = useRef<HTMLDivElement>(null);
  const parsed = parseTheme(theme).theme;
  useEffect(() => {
    if (!frame.current || !parsed) return;
    applyToDocument(
      {
        theme: parsed,
        scheme: parsed.colorScheme,
        requestedTheme: null,
        fallback: false,
        reducedMotion: false,
        textScale: 1,
        overlay: null,
      },
      preferences,
      frame.current,
    );
  }, [parsed, preferences]);
  return (
    <div ref={frame} className="theme-preview">
      {parsed ? <ThemeMiniature theme={parsed} /> : null}
      <div className="theme-preview__header">
        <span className="theme-preview__avatar" aria-hidden="true">
          A
        </span>
        <span className="ds-level">7</span>
        <span className="ds-coins">
          <Icon name="coins" size={14} />
          390
        </span>
      </div>
      <article className="ds-card theme-preview__card">
        <strong>{t("admin:studio.preview.title")}</strong>
        <p>{t("admin:studio.preview.text")}</p>
        <div className="theme-preview__buttons">
          <span className="ds-button ds-button--primary">{t("admin:studio.preview.button")}</span>
          <span className="ds-button ds-button--secondary">{t("admin:studio.preview.secondary")}</span>
        </div>
        <div className="theme-preview__chips">
          {(["available", "partial", "unavailable"] as const).map((state) => (
            <span
              key={state}
              className="ds-badge"
              style={{ background: `var(--state-${state}-bg)`, color: `var(--state-${state}-fg)` }}
            >
              {t(`admin:cc.state.${state}`)}
            </span>
          ))}
          {RARITIES.map((rarity) => (
            <span key={rarity} className="ds-badge" style={{ color: `var(--rarity-${rarity})` }}>
              ★ {rarity}
            </span>
          ))}
        </div>
      </article>
    </div>
  );
}

function SellDialog({
  theme,
  onClose,
  onDone,
}: {
  theme: AdminTheme;
  onClose: () => void;
  onDone: () => void;
}) {
  const t = useT();
  const [price, setPrice] = useState(250);
  const [rarity, setRarity] = useState<(typeof RARITIES)[number]>("rare");
  const [effect, setEffect] = useState("auto");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState<{ ok: boolean; text: string } | null>(null);
  const productKey = `theme_${theme.key.replace(/-/g, "_")}`;
  const sell = useMutation({
    mutationFn: async () => {
      await api.POST("/api/v1/admin/marketplace/products", {
        body: {
          definition: {
            key: productKey,
            type: "theme",
            presentation: { rarity, poster_effect: effect, icon: "palette" },
            version: {
              names: { en: theme.name, fr: theme.name },
              descriptions: description ? { en: description, fr: description } : {},
              price_coins: price,
              payload: { theme: theme.key },
            },
          },
        } as never,
      });
      await withConfirmation(
        (confirmation) =>
          api.POST("/api/v1/admin/marketplace/products/{key}/{transition}", {
            params: { path: { key: productKey, transition: "publish" } },
            body: { confirmation: confirmation ?? null },
          }),
        () => true, // the administrator asked to publish: the dialog is the confirmation
      );
    },
    onSuccess: () => {
      setStatus({ ok: true, text: t("admin:studio.sell.done") });
      onDone();
    },
    onError: (e) => setStatus({ ok: false, text: t("admin:studio.sell.failed", { detail: errorDetail(e) }) }),
  });
  return (
    <Dialog
      open
      onOpenChange={(open) => (open ? null : onClose())}
      title={t("admin:studio.sell.title", { name: theme.name })}
      description={t("admin:studio.sell.hint")}
      trigger={<span hidden />}
    >
      <form
        className="theme-studio__sell"
        onSubmit={(event) => {
          event.preventDefault();
          sell.mutate();
        }}
      >
        <TextField
          label={t("admin:studio.sell.price")}
          type="number"
          min={0}
          value={price}
          onChange={(event) => setPrice(Math.max(0, Number(event.target.value)))}
        />
        <Choice
          label={t("admin:studio.sell.rarity")}
          value={rarity}
          options={RARITIES}
          labels={Object.fromEntries(RARITIES.map((r) => [r, t(`marketplace:rarity.${r}`)]))}
          onChange={setRarity}
        />
        <Choice
          label={t("admin:studio.sell.effect")}
          value={effect}
          options={["auto", "none", "shine", "glitch", "spin", "neon", "blink"] as const}
          labels={{
            auto: t("marketplace:effect.auto"),
            none: t("marketplace:effect.none"),
            shine: t("marketplace:effect.shine"),
            glitch: t("marketplace:effect.glitch"),
            spin: t("marketplace:effect.spin"),
            neon: t("marketplace:effect.neon"),
            blink: t("marketplace:effect.blink"),
          }}
          onChange={setEffect}
        />
        <TextField
          label={t("admin:studio.sell.description")}
          value={description}
          maxLength={300}
          onChange={(event) => setDescription(event.target.value)}
        />
        {status ? (
          <p role={status.ok ? "status" : "alert"} data-ok={status.ok}>
            {status.text}
          </p>
        ) : null}
        <DialogActions>
          <Button type="submit" disabled={sell.isPending || Boolean(status?.ok)}>
            <Icon name="shop" size={16} />
            {t("admin:studio.sell.publish")}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
