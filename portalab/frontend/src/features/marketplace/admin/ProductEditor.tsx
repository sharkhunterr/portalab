import { useState } from "react";
import { api } from "../../../api/client";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, SelectField, TextField } from "../../../design-system/components/Field";
import { ICONS, Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { useTheme } from "../../../design-system/themes/ThemeProvider";
import { useT } from "../../../i18n/hooks/useT";
import type { Category, Product } from "../api";
import { ProductPoster } from "../catalog/ProductPoster";

/**
 * Product editors (spec 027 US8): a real form instead of a JSON definition — the fields follow the product
 * type — and the shop presentation (rarity, poster animation, featured, collection, icon) with a live poster.
 */
export const RARITIES = ["common", "rare", "epic", "legendary"] as const;
export const EFFECTS = ["auto", "none", "shine", "glitch", "spin", "neon", "blink"] as const;
const TYPES = ["badge", "title", "effect", "theme", "quota", "feature", "widget", "statistic"] as const;
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
        label={t("marketplace:admin.posterEffect")}
        value={value.poster_effect}
        onChange={(e) =>
          onChange({ ...value, poster_effect: e.target.value as Presentation["poster_effect"] })
        }
      >
        {EFFECTS.map((effect) => (
          <option key={effect} value={effect}>
            {t(`marketplace:effect.${effect}`)}
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
          <ProductPoster product={preview} />
        </div>
        <PresentationFields
          value={value}
          category={category}
          categories={categories}
          onChange={setValue}
          onCategory={setCategory}
        />
      </div>
      {error ? <p role="alert">{t("marketplace:admin.error")}</p> : null}
      <Button
        onClick={async () => {
          try {
            await api.PUT("/api/v1/admin/marketplace/products/{key}/presentation", {
              params: { path: { key: product.key } },
              body: { presentation: value, category: category || null },
            });
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
  onCreated,
}: {
  categories: readonly Category[];
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
  const [effect, setEffect] = useState("");
  const [theme, setTheme] = useState("");
  const [units, setUnits] = useState(5);
  const [extra, setExtra] = useState("{}");
  const [presentation, setPresentation] = useState<Presentation>(DEFAULT_PRESENTATION);
  const [category, setCategory] = useState("");
  const [error, setError] = useState<string | null>(null);
  const payload = (): Record<string, unknown> => {
    switch (type) {
      case "badge":
        return { label, icon };
      case "title":
        return { label };
      case "effect":
        return { effect };
      case "theme":
        return { theme };
      case "quota":
        return { kind: "media_requests", units };
      default:
        return JSON.parse(extra || "{}") as Record<string, unknown>;
    }
  };
  const preview = { key, type, name: nameEn, ...presentation, price_coins: price } as unknown as Product;
  const submit = async () => {
    setError(null);
    try {
      await api.POST("/api/v1/admin/marketplace/products", {
        body: {
          definition: {
            key,
            type,
            ...(category ? { category } : {}),
            presentation,
            version: {
              price_coins: price,
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
          <ProductPoster product={preview} />
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
          {type === "effect" ? (
            <TextField
              label={t("marketplace:admin.effect")}
              value={effect}
              required
              onChange={(e) => setEffect(e.target.value)}
            />
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
        {error ? <p role="alert">{error}</p> : null}
        <Button type="submit" disabled={!key || !nameEn}>
          {t("marketplace:admin.create")}
        </Button>
      </form>
    </Dialog>
  );
}
