import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../../api/client";
import {
  AMBIENTS,
  CELEBRATION_KEYS,
  LEVEL_BADGES,
  LEVEL_UPS,
  NOTIFICATION_ANIMATIONS,
  NOTIFICATION_STYLES,
  PALETTE_KEYS,
} from "../../../design-system/a11y/preferences";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, SelectField, TextField } from "../../../design-system/components/Field";
import { ICONS, Icon } from "../../../design-system/components/Icon";
import { Dialog, DialogActions } from "../../../design-system/components/Overlays";
import { BANNER_KEYS, FRAME_KEYS, NAME_KEYS } from "../../../design-system/themes/cosmetics";
import { useTheme } from "../../../design-system/themes/ThemeProvider";
import { useT } from "../../../i18n/hooks/useT";
import type { Category, Product } from "../api";
import { ProductArt } from "../catalog/ProductArt";
import { withConfirmation } from "./confirm";

/**
 * Product editors (spec 027 US8): a real form instead of a JSON definition — the fields follow the product
 * type — and the shop presentation (rarity, featured, collection, icon) with a live poster;
 * 027: availability (copies, purchase limit per period, minimum level).
 */
export const RARITIES = ["common", "rare", "epic", "legendary"] as const;
export const EFFECTS = ["auto", "none", "shine", "glitch", "spin", "neon", "blink"] as const;
const TYPES = [
  "badge",
  "title",
  "effect",
  "ambient",
  "theme",
  "palette",
  "notification_style",
  "notification_animation",
  "profile_banner",
  "avatar_frame",
  "profile_background",
  "name_style",
  "level_badge",
  "level_up",
  "widget",
  "bundle",
  "quota",
  "feature",
  "statistic",
  // 027: requests the administrators handle (a film in 4K…) and a homelab service's access
  "special_request",
  "service_access",
  // #54/#55: consumable perks — streak freezes and gains boosts
  "streak_freeze",
  "xp_boost",
] as const;
/** 027: the designs each cosmetic type can sell (keys shared with the backend). */
const DESIGNS: Partial<
  Record<(typeof TYPES)[number], { field: string; values: readonly string[]; ns: string }>
> = {
  effect: { field: "effect", values: CELEBRATION_KEYS, ns: "notifications:universe.celebrations" },
  ambient: { field: "ambient", values: AMBIENTS, ns: "notifications:universe.ambients" },
  profile_background: { field: "background", values: AMBIENTS, ns: "notifications:universe.ambients" },
  palette: { field: "palette", values: PALETTE_KEYS, ns: "notifications:palette.names" },
  profile_banner: { field: "banner", values: BANNER_KEYS, ns: "community:looks.banner" },
  avatar_frame: { field: "frame", values: FRAME_KEYS, ns: "community:looks.frame" },
  name_style: { field: "style", values: NAME_KEYS, ns: "community:looks.name" },
  level_badge: { field: "style", values: LEVEL_BADGES, ns: "notifications:levelBadge.names" },
  level_up: { field: "animation", values: LEVEL_UPS, ns: "notifications:levelUp.names" },
};
const BADGE_STYLES = [
  "none",
  "shimmer",
  "pulse",
  "flame",
  "glitch",
  "rainbow",
  "float",
  "spin",
  "frost",
  "neon",
  "gold",
  "vhs",
  "pixel",
  "terminal",
  "water",
  "wind",
  "saber",
  "veins",
  "mirror",
  "ring",
  "elven",
  "glass",
  "hazard",
];
const ICON_NAMES = Object.keys(ICONS).sort();

export interface Presentation {
  rarity: (typeof RARITIES)[number];
  poster_effect: (typeof EFFECTS)[number];
  featured: boolean;
  icon: string | null;
}

function PresentationFields({
  value,
  category,
  categories,
  onChange,
  onCategory,
}: {
  value: Presentation;
  category: string;
  categories: readonly Category[];
  onChange: (value: Presentation) => void;
  onCategory: (key: string) => void;
}) {
  const t = useT();
  return (
    <fieldset className="product-editor__fields">
      <legend>{t("marketplace:admin.presentation")}</legend>
      <SelectField
        label={t("marketplace:shop.rarity")}
        value={value.rarity}
        onChange={(e) => onChange({ ...value, rarity: e.target.value as Presentation["rarity"] })}
      >
        {RARITIES.map((r) => (
          <option key={r} value={r}>
            {t(`marketplace:rarity.${r}`)}
          </option>
        ))}
      </SelectField>
      <SelectField
        label={t("marketplace:admin.collection")}
        value={category}
        onChange={(e) => onCategory(e.target.value)}
      >
        <option value="">{t("marketplace:admin.noCollection")}</option>
        {categories.map((c) => (
          <option key={c.key} value={c.key}>
            {t(c.label_key)}
          </option>
        ))}
      </SelectField>
      <SelectField
        label={t("marketplace:admin.icon")}
        value={value.icon ?? ""}
        onChange={(e) => onChange({ ...value, icon: e.target.value || null })}
      >
        <option value="">—</option>
        {ICON_NAMES.map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </SelectField>
      <CheckboxField
        label={t("marketplace:admin.featured")}
        checked={value.featured}
        onChange={(e) => onChange({ ...value, featured: e.target.checked })}
      />
    </fieldset>
  );
}

/** 027: copies (empty: from the rarity), purchase limit per period, minimum level — as typed. */
export interface AvailabilityForm {
  supply: string;
  limitCount: string;
  limitDays: string;
  minLevel: string;
  /** 027: Contribution points needed (to keep a product for those who take part) */
  minContribution: string;
}

const EMPTY_AVAILABILITY: AvailabilityForm = {
  supply: "",
  limitCount: "",
  limitDays: "",
  minLevel: "",
  minContribution: "",
};

function numberOrNull(value: string): number | null {
  const parsed = Number(value);
  return value.trim() && Number.isFinite(parsed) && parsed >= 1 ? Math.floor(parsed) : null;
}

/** 027: one field of a special request's form, as the administrator writes it. */
interface FormFieldDraft {
  label: string;
  type: "text" | "textarea" | "choice" | "multi" | "boolean";
  options: string;
  required: boolean;
}

function slug(text: string, index: number): string {
  const base = text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return /^[a-z]/.test(base) ? base.slice(0, 40) : `field_${index + 1}`;
}

export function formOf(fields: FormFieldDraft[]) {
  return fields
    .filter((f) => f.label.trim())
    .map((f, index) => ({
      key: slug(f.label, index),
      type: f.type,
      labels: { en: f.label.trim(), fr: f.label.trim() },
      options: f.options
        .split(",")
        .map((o) => o.trim())
        .filter(Boolean),
      required: f.required,
    }));
}

/** 027: the questions a special request asks once bought (a film in 4K: which film, sound, languages…). */
function FormBuilder({
  value,
  onChange,
}: {
  value: FormFieldDraft[];
  onChange: (value: FormFieldDraft[]) => void;
}) {
  const t = useT();
  const set = (index: number, patch: Partial<FormFieldDraft>) =>
    onChange(value.map((f, i) => (i === index ? { ...f, ...patch } : f)));
  return (
    <fieldset className="product-editor__form">
      <legend>{t("marketplace:admin.form")}</legend>
      <p className="ds-field__hint">{t("marketplace:admin.formHint")}</p>
      {value.map((field, index) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: rows the administrator adds and removes in place
        <div key={index} className="product-editor__form-row">
          <TextField
            label={t("marketplace:admin.fieldLabel")}
            value={field.label}
            onChange={(e) => set(index, { label: e.target.value })}
          />
          <SelectField
            label={t("marketplace:admin.fieldType")}
            value={field.type}
            onChange={(e) => set(index, { type: e.target.value as FormFieldDraft["type"] })}
          >
            {(["text", "textarea", "choice", "multi", "boolean"] as const).map((kind) => (
              <option key={kind} value={kind}>
                {t(`marketplace:admin.fieldTypes.${kind}`)}
              </option>
            ))}
          </SelectField>
          {field.type === "choice" || field.type === "multi" ? (
            <TextField
              label={t("marketplace:admin.fieldOptions")}
              value={field.options}
              onChange={(e) => set(index, { options: e.target.value })}
            />
          ) : null}
          <label className="request-form__choice">
            <input
              type="checkbox"
              checked={field.required}
              onChange={(e) => set(index, { required: e.target.checked })}
            />
            {t("marketplace:admin.fieldRequired")}
          </label>
          <Button
            variant="ghost"
            size="icon"
            aria-label={t("marketplace:admin.fieldRemove")}
            onClick={() => onChange(value.filter((_, i) => i !== index))}
          >
            <Icon name="trash" size={16} />
          </Button>
        </div>
      ))}
      <Button
        variant="secondary"
        onClick={() => onChange([...value, { label: "", type: "text", options: "", required: false }])}
      >
        <Icon name="plus" size={16} />
        {t("marketplace:admin.fieldAdd")}
      </Button>
    </fieldset>
  );
}

/** 027: which homelab service a purchase opens, and the identity provider's group that grants it. */
function ServiceAccessFields({
  service,
  group,
  onService,
  onGroup,
}: {
  service: string;
  group: string;
  onService: (value: string) => void;
  onGroup: (value: string) => void;
}) {
  const t = useT();
  const services = useQuery({
    queryKey: ["admin", "services"],
    queryFn: async () =>
      ((await api.GET("/api/v1/services")).data as unknown as { items: Array<{ id: string; name: string }> })
        .items,
  });
  return (
    <>
      <SelectField
        label={t("marketplace:admin.service")}
        value={service}
        onChange={(e) => onService(e.target.value)}
      >
        <option value="">—</option>
        {(services.data ?? []).map((item) => (
          <option key={item.id} value={item.id}>
            {item.name}
          </option>
        ))}
      </SelectField>
      <TextField
        label={t("marketplace:admin.group")}
        hint={t("marketplace:admin.groupHint")}
        value={group}
        onChange={(e) => onGroup(e.target.value)}
      />
    </>
  );
}

export function availabilityBody(value: AvailabilityForm) {
  const count = numberOrNull(value.limitCount);
  const days = numberOrNull(value.limitDays);
  return {
    availability: {
      supply: numberOrNull(value.supply),
      limit_count: count && days ? count : null,
      limit_days: count && days ? days : null,
    },
    min_level: numberOrNull(value.minLevel),
    min_contribution: numberOrNull(value.minContribution),
  };
}

function AvailabilityFields({
  value,
  onChange,
}: {
  value: AvailabilityForm;
  onChange: (value: AvailabilityForm) => void;
}) {
  const t = useT();
  const field = (key: keyof AvailabilityForm, label: string, max: number) => (
    <TextField
      label={label}
      type="number"
      min={1}
      max={max}
      value={value[key]}
      onChange={(e) => onChange({ ...value, [key]: e.target.value })}
    />
  );
  return (
    <fieldset className="product-editor__fields">
      <legend>{t("marketplace:admin.availability")}</legend>
      {field("supply", t("marketplace:admin.supply"), 1000000)}
      {field("minLevel", t("marketplace:admin.minLevel"), 1000)}
      {field("minContribution", t("marketplace:admin.minContribution"), 1000000)}
      {field("limitCount", t("marketplace:admin.limitCount"), 1000)}
      {field("limitDays", t("marketplace:admin.limitDays"), 366)}
      <p className="ds-field__hint">{t("marketplace:admin.repeatHint")}</p>
    </fieldset>
  );
}

const DEFAULT_PRESENTATION: Presentation = {
  rarity: "common",
  poster_effect: "auto",
  featured: false,
  icon: null,
};

/** Shop presentation of an existing product: merchandising only, no new price version. */
export function PresentationDialog({
  product,
  categories,
  onSaved,
}: {
  product: Product;
  categories: readonly Category[];
  onSaved: () => void;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState<Presentation>(DEFAULT_PRESENTATION);
  const [category, setCategory] = useState("");
  const [availability, setAvailability] = useState<AvailabilityForm>(EMPTY_AVAILABILITY);
  const [error, setError] = useState(false);
  const preview = { ...product, ...value } as Product;
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) {
          setValue({
            rarity: (product.rarity ?? "common") as Presentation["rarity"],
            poster_effect: (product.poster_effect ?? "auto") as Presentation["poster_effect"],
            featured: Boolean(product.featured),
            icon: product.icon ?? null,
          });
          setCategory(product.category ?? "");
          setAvailability({
            supply: product.supply ? String(product.supply) : "",
            limitCount: product.limit_count ? String(product.limit_count) : "",
            limitDays: product.limit_days ? String(product.limit_days) : "",
            minLevel: product.min_level ? String(product.min_level) : "",
            minContribution: product.min_contribution ? String(product.min_contribution) : "",
          });
          setError(false);
        }
      }}
      title={`${t("marketplace:admin.edit")} · ${product.name}`}
      closeLabel={t("marketplace:admin.cancel")}
      trigger={
        <Button
          variant="secondary"
          size="icon"
          aria-label={t("marketplace:admin.edit")}
          title={t("marketplace:admin.edit")}
        >
          <Icon name="palette" size={18} />
        </Button>
      }
    >
      <div className="product-editor">
        <div className="product-editor__preview" data-rarity={value.rarity}>
          <ProductArt product={preview} />
        </div>
        <PresentationFields
          value={value}
          category={category}
          categories={categories}
          onChange={setValue}
          onCategory={setCategory}
        />
        <AvailabilityFields value={availability} onChange={setAvailability} />
      </div>
      {error ? <p role="alert">{t("marketplace:admin.error")}</p> : null}
      <Button
        onClick={async () => {
          try {
            await api.PUT("/api/v1/admin/marketplace/products/{key}/presentation", {
              params: { path: { key: product.key } },
              body: { presentation: value, category: category || null },
            });
            await withConfirmation(
              (confirmation) =>
                api.PUT("/api/v1/admin/marketplace/products/{key}/availability", {
                  params: { path: { key: product.key } },
                  body: { ...availabilityBody(availability), confirmation: confirmation ?? null },
                }),
              () => window.confirm(t("marketplace:admin.confirm")),
            );
            setOpen(false);
            onSaved();
          } catch {
            setError(true);
          }
        }}
      >
        {t("marketplace:admin.save")}
      </Button>
    </Dialog>
  );
}

/** New product: the payload fields follow the type; advanced settings stay available as JSON. */
export function NewProductDialog({
  categories,
  products = [],
  onCreated,
}: {
  categories: readonly Category[];
  /** 027: what a pack may contain. */
  products?: readonly Product[];
  onCreated: () => void;
}) {
  const t = useT();
  const { themes } = useTheme();
  const [open, setOpen] = useState(false);
  const [type, setType] = useState<(typeof TYPES)[number]>("badge");
  const [key, setKey] = useState("");
  const [nameEn, setNameEn] = useState("");
  const [nameFr, setNameFr] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState(100);
  const [label, setLabel] = useState("");
  const [icon, setIcon] = useState("star");
  const [theme, setTheme] = useState("");
  const [units, setUnits] = useState(5);
  const [look, setLook] = useState("");
  const [widget, setWidget] = useState("");
  const [design, setDesign] = useState("");
  const [style, setStyle] = useState("none");
  const [packed, setPacked] = useState<string[]>([]);
  const [extra, setExtra] = useState("{}");
  const [deadline, setDeadline] = useState(7);
  const [factor, setFactor] = useState(1.5);
  const [hours, setHours] = useState(24);
  const [fields, setFields] = useState<FormFieldDraft[]>([
    { label: "", type: "text", options: "", required: true },
  ]);
  const [service, setService] = useState("");
  const [group, setGroup] = useState("");
  const [presentation, setPresentation] = useState<Presentation>(DEFAULT_PRESENTATION);
  const [availability, setAvailability] = useState<AvailabilityForm>(EMPTY_AVAILABILITY);
  const [category, setCategory] = useState("");
  const [error, setError] = useState<string | null>(null);
  const payload = (): Record<string, unknown> => {
    switch (type) {
      case "badge":
        return { label, icon, ...(style !== "none" ? { style } : {}) };
      case "title":
        return { label, ...(style !== "none" ? { style } : {}) };
      case "theme":
        return { theme };
      case "quota":
        return { kind: "media_requests", units };
      case "notification_style":
        return { style: look };
      case "notification_animation":
        return { animation: look };
      case "widget":
        return { widget };
      case "bundle":
        return { products: packed };
      case "special_request":
        return { deadline_days: deadline, form: formOf(fields) };
      case "service_access":
        return { deadline_days: deadline, service, ...(group.trim() ? { group: group.trim() } : {}) };
      case "streak_freeze":
        return { count: units };
      case "xp_boost":
        return { factor, hours, values: ["xp"] };
      default:
        {
          const designed = DESIGNS[type];
          if (designed) return { [designed.field]: design };
        }
        return JSON.parse(extra || "{}") as Record<string, unknown>;
    }
  };
  const safePayload = () => {
    try {
      return payload();
    } catch {
      return {};
    }
  };
  const preview = {
    key,
    type,
    name: nameEn,
    ...presentation,
    price_coins: price,
    descriptions: {},
    preview: safePayload(),
  } as unknown as Product;
  const submit = async () => {
    setError(null);
    if (type === "bundle" && !packed.length) {
      setError(t("marketplace:admin.packEmpty"));
      return;
    }
    try {
      await api.POST("/api/v1/admin/marketplace/products", {
        body: {
          definition: {
            key,
            type,
            ...(category ? { category } : {}),
            presentation,
            ...(() => {
              const body = availabilityBody(availability);
              return {
                availability: body.availability,
                repeatable: ["quota", "streak_freeze", "xp_boost"].includes(type),
              };
            })(),
            version: {
              price_coins: price,
              conditions: [
                ...(numberOrNull(availability.minLevel)
                  ? [{ kind: "min_level", level: numberOrNull(availability.minLevel) }]
                  : []),
                ...(numberOrNull(availability.minContribution)
                  ? [{ kind: "min_contribution", contribution: numberOrNull(availability.minContribution) }]
                  : []),
              ],
              names: { en: nameEn, ...(nameFr ? { fr: nameFr } : {}) },
              descriptions: description ? { en: description } : {},
              payload: payload(),
            },
          },
        },
      });
      setOpen(false);
      onCreated();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : t("marketplace:admin.error"));
    }
  };
  return (
    <Dialog
      open={open}
      onOpenChange={setOpen}
      title={t("marketplace:admin.new")}
      closeLabel={t("marketplace:admin.cancel")}
      trigger={
        <Button>
          <Icon name="plus" size={18} />
          {t("marketplace:admin.new")}
        </Button>
      }
    >
      <form
        className="product-editor"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <div className="product-editor__preview" data-rarity={presentation.rarity}>
          <ProductArt product={preview} />
        </div>
        <fieldset className="product-editor__fields">
          <SelectField
            label={t("marketplace:admin.type")}
            value={type}
            onChange={(e) => setType(e.target.value as (typeof TYPES)[number])}
          >
            {TYPES.map((value) => (
              <option key={value} value={value}>
                {t(`marketplace:type.${value}`)}
              </option>
            ))}
          </SelectField>
          <TextField
            label={t("marketplace:admin.key")}
            value={key}
            required
            pattern="[a-z][a-z0-9_]*"
            onChange={(e) => setKey(e.target.value)}
          />
          <TextField
            label={t("marketplace:admin.nameEn")}
            value={nameEn}
            required
            onChange={(e) => setNameEn(e.target.value)}
          />
          <TextField
            label={t("marketplace:admin.nameFr")}
            value={nameFr}
            onChange={(e) => setNameFr(e.target.value)}
          />
          <TextField
            label={t("marketplace:admin.description")}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <TextField
            label={t("marketplace:admin.price")}
            type="number"
            min={0}
            max={1000000}
            value={String(price)}
            onChange={(e) => setPrice(Number(e.target.value))}
          />
          {type === "badge" || type === "title" ? (
            <TextField
              label={t("marketplace:admin.label")}
              value={label}
              required
              onChange={(e) => setLabel(e.target.value)}
            />
          ) : null}
          {type === "badge" ? (
            <SelectField
              label={t("marketplace:admin.icon")}
              value={icon}
              onChange={(e) => setIcon(e.target.value)}
            >
              {ICON_NAMES.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </SelectField>
          ) : null}
          {type === "badge" || type === "title" ? (
            <SelectField
              label={t("marketplace:admin.style")}
              value={style}
              onChange={(e) => setStyle(e.target.value)}
            >
              {BADGE_STYLES.map((value) => (
                <option key={value} value={value}>
                  {t(`marketplace:badgeStyle.${value}`)}
                </option>
              ))}
            </SelectField>
          ) : null}
          {DESIGNS[type] ? (
            <SelectField
              label={t("marketplace:admin.design")}
              value={design}
              required
              onChange={(e) => setDesign(e.target.value)}
            >
              <option value="">—</option>
              {(DESIGNS[type]?.values ?? [])
                .filter((value) => value !== "none" && value !== "theme")
                .map((value) => (
                  <option key={value} value={value}>
                    {t(`${DESIGNS[type]?.ns}.${value}`)}
                  </option>
                ))}
            </SelectField>
          ) : null}
          {type === "notification_style" || type === "notification_animation" ? (
            <SelectField
              label={t(
                type === "notification_style" ? "marketplace:admin.style" : "marketplace:admin.animation",
              )}
              value={look}
              required
              onChange={(e) => setLook(e.target.value)}
            >
              <option value="">—</option>
              {(type === "notification_style" ? NOTIFICATION_STYLES : NOTIFICATION_ANIMATIONS).map(
                (value) => (
                  <option key={value} value={value}>
                    {t(
                      `notifications:looks.${type === "notification_style" ? "styles" : "animations"}.${value}`,
                    )}
                  </option>
                ),
              )}
            </SelectField>
          ) : null}
          {type === "widget" ? (
            <TextField
              label={t("marketplace:admin.widget")}
              value={widget}
              required
              pattern="[a-z][a-z0-9_.:-]*"
              placeholder="media.poster_wall"
              onChange={(e) => setWidget(e.target.value)}
            />
          ) : null}
          {type === "bundle" ? (
            <fieldset className="product-editor__pack">
              <legend>{t("marketplace:admin.packProducts")}</legend>
              <p className="ds-field__hint">{t("marketplace:admin.packHint")}</p>
              {products
                .filter((p) => p.type !== "bundle")
                .map((p) => (
                  <CheckboxField
                    key={p.key}
                    label={`${p.name} · ${t(`marketplace:type.${p.type}`)}`}
                    checked={packed.includes(p.key)}
                    onChange={(e) =>
                      setPacked(e.target.checked ? [...packed, p.key] : packed.filter((k) => k !== p.key))
                    }
                  />
                ))}
            </fieldset>
          ) : null}
          {type === "theme" ? (
            <SelectField
              label={t("marketplace:admin.theme")}
              value={theme}
              required
              onChange={(e) => setTheme(e.target.value)}
            >
              <option value="">—</option>
              {themes.map((item) => (
                <option key={item.key} value={item.key}>
                  {item.name}
                </option>
              ))}
            </SelectField>
          ) : null}
          {type === "quota" ? (
            <TextField
              label={t("marketplace:admin.units")}
              type="number"
              min={1}
              max={100}
              value={String(units)}
              onChange={(e) => setUnits(Number(e.target.value))}
            />
          ) : null}
          {type === "streak_freeze" ? (
            <TextField
              label={t("marketplace:admin.freezes")}
              type="number"
              min={1}
              max={30}
              value={String(units)}
              onChange={(e) => setUnits(Number(e.target.value))}
            />
          ) : null}
          {type === "xp_boost" ? (
            <>
              <TextField
                label={t("marketplace:admin.boostFactor")}
                type="number"
                min={1.1}
                max={5}
                step={0.1}
                value={String(factor)}
                onChange={(e) => setFactor(Number(e.target.value))}
              />
              <TextField
                label={t("marketplace:admin.boostHours")}
                type="number"
                min={1}
                max={720}
                value={String(hours)}
                onChange={(e) => setHours(Number(e.target.value))}
              />
            </>
          ) : null}
          {type === "special_request" || type === "service_access" ? (
            <TextField
              label={t("marketplace:admin.deadline")}
              type="number"
              min={1}
              max={365}
              value={String(deadline)}
              onChange={(e) => setDeadline(Number(e.target.value))}
            />
          ) : null}
          {type === "special_request" ? <FormBuilder value={fields} onChange={setFields} /> : null}
          {type === "service_access" ? (
            <ServiceAccessFields service={service} group={group} onService={setService} onGroup={setGroup} />
          ) : null}
          {["feature", "widget", "statistic"].includes(type) ? (
            <div className="ds-field">
              <label htmlFor="product-extra">{t("marketplace:admin.extra")}</label>
              <textarea
                id="product-extra"
                rows={4}
                value={extra}
                onChange={(e) => setExtra(e.target.value)}
              />
            </div>
          ) : null}
        </fieldset>
        <PresentationFields
          value={presentation}
          category={category}
          categories={categories}
          onChange={setPresentation}
          onCategory={setCategory}
        />
        <AvailabilityFields value={availability} onChange={setAvailability} />
        {error ? <p role="alert">{error}</p> : null}
        <DialogActions>
          <Button type="submit" disabled={!key || !nameEn}>
            {t("marketplace:admin.create")}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
