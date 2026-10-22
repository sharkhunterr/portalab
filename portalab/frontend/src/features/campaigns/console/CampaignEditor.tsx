import { useQueries, useQuery } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { api } from "../../../api/client";
import { FormActions, FormGrid, SearchBox } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { type Campaign, useCampaignAdmin } from "../api";

/**
 * Campaign editor (027): a form instead of raw JSON — names, dates (wall clock in the campaign's time zone,
 * once or every year), **bonuses** (a value multiplied for some actions, media kinds and genres, e.g. ×2 XP
 * for horror films and series; or Christmas films — by title, by the provider's keywords or hand-picked) and
 * **shop discounts** (a percentage off chosen products, categories or a whole season).
 * Parts the form does not edit (scoped achievements and quests, theme) are kept as they are.
 */
type Value = "xp" | "coins" | "contribution";

export interface Gain {
  value: Value;
  factor: number;
}

export interface Bonus {
  id: string;
  /** One value multiplied (older bonuses) — or several, in ``gains``. */
  value?: Value;
  factor?: number;
  gains?: Gain[];
  when: {
    activity?: string[];
    media_kind?: string[];
    genre?: string[];
    title_contains?: string[];
    keyword?: string[];
    objects?: string[];
    audience?: unknown;
  };
}

export interface Discount {
  id: string;
  percent: number;
  products: string[];
  categories: string[];
  seasons?: string[];
  /** The whole shop (a larger reduction on some products still wins for them). */
  everything?: boolean;
}

export interface CampaignDef {
  names: Record<string, string>;
  description?: string;
  timezone?: string;
  schedule: {
    start_at: string;
    end_at?: string | null;
    duration_hours?: number | null;
    recurrence?: { kind: "none" | "yearly" | "custom"; [key: string]: unknown };
  };
  modifiers?: Bonus[];
  discounts?: Discount[];
  ending_soon_hours?: number | null;
  [key: string]: unknown;
}

export const ACTIONS = [
  "media.playback_finished",
  "media.request_created",
  "media.request_watched",
  "marketplace.purchase",
  "ticket.created",
  "feedback.submitted",
  "user.signed_in",
];
export const MEDIA_KINDS = ["movie", "series", "episode", "book", "audiobook", "game", "album"];
const VALUES: Value[] = ["xp", "coins", "contribution"];
/** The shop's seasons (a product of a season — its looks, its booster, its pack — carries its key). */
export const SEASONS = ["valentine", "spring", "summer", "halloween", "christmas"];

const list = (text: string) =>
  text
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);

function blankBonus(index: number): Bonus {
  return {
    id: `bonus_${index + 1}`,
    gains: [{ value: "xp", factor: 2 }],
    when: { activity: ["media.playback_finished"] },
  };
}

/** Every value a bonus multiplies (its single ``value`` × ``factor`` for an older one). */
export function gainsOf(bonus: Bonus): Gain[] {
  if (bonus.gains?.length) return bonus.gains;
  return bonus.value ? [{ value: bonus.value, factor: bonus.factor ?? 1 }] : [];
}

interface ShopProduct {
  key: string;
  name: string;
  state: string;
  category?: string | null;
  price_coins?: number | null;
}

function useShop() {
  const products = useQuery({
    queryKey: ["campaigns", "admin", "shop"],
    queryFn: async () =>
      ((await api.GET("/api/v1/admin/marketplace/products")).data ?? []) as unknown as ShopProduct[],
    staleTime: 60_000,
  });
  const categories = useQuery({
    queryKey: ["campaigns", "admin", "shop-categories"],
    queryFn: async () =>
      ((await api.GET("/api/v1/marketplace/categories")).data ?? []) as unknown as Array<{
        key: string;
        label_key: string;
      }>,
    staleTime: 60_000,
  });
  return { products: products.data ?? [], categories: categories.data ?? [] };
}

interface MediaHit {
  id: string;
  title: string;
  kind: string;
  year?: number | null;
}

/** Hand-picked titles: found in the library by name; a series counts its episodes. */
function PickedTitles({ ids, onChange }: { ids: string[]; onChange: (ids: string[]) => void }) {
  const t = useT();
  const [query, setQuery] = useState("");
  const found = useQuery({
    queryKey: ["campaigns", "admin", "media", query.trim()],
    enabled: query.trim().length >= 2,
    queryFn: async () =>
      ((await api.GET("/api/v1/media", { params: { query: { q: query.trim() } } })).data?.items ?? [])
        .filter((item) => ["movie", "series", "book", "audiobook", "game", "album"].includes(item.kind))
        .slice(0, 8) as unknown as MediaHit[],
  });
  const picked = useQueries({
    queries: ids.map((id) => ({
      queryKey: ["campaigns", "admin", "media-item", id],
      staleTime: 300_000,
      queryFn: async () =>
        (await api.GET("/api/v1/media/{object_id}", { params: { path: { object_id: id } } })).data as
          | MediaHit
          | undefined,
    })),
  });
  return (
    <fieldset className="campaign-bonus__group">
      <legend>{t("campaigns:editor.picked", { count: ids.length })}</legend>
      {ids.length ? (
        <ul className="campaign-picked">
          {ids.map((id, index) => (
            <li key={id}>
              <span>{picked[index]?.data?.title ?? id.slice(0, 8)}</span>
              <button
                type="button"
                aria-label={t("campaigns:editor.unpick", { title: picked[index]?.data?.title ?? id })}
                onClick={() => onChange(ids.filter((x) => x !== id))}
              >
                <Icon name="close" size={14} />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <SearchBox label={t("campaigns:editor.findTitle")} value={query} onChange={setQuery} />
      {found.data?.length ? (
        <ul className="campaign-found">
          {found.data.map((hit) => (
            <li key={hit.id}>
              <span>
                {hit.title}
                <span className="admin-muted">
                  {" "}
                  · {t(`media:kind.${hit.kind}`)}
                  {hit.year ? ` · ${hit.year}` : ""}
                </span>
              </span>
              <Button
                variant="ghost"
                disabled={ids.includes(hit.id)}
                onClick={() => onChange([...ids, hit.id])}
              >
                <Icon name="plus" size={14} />
                {t("campaigns:editor.pick")}
              </Button>
            </li>
          ))}
        </ul>
      ) : null}
    </fieldset>
  );
}

function BonusEditor({
  bonus,
  onChange,
  onRemove,
}: {
  bonus: Bonus;
  onChange: (next: Bonus) => void;
  onRemove: () => void;
}) {
  const t = useT();
  const when = bonus.when;
  const gains = gainsOf(bonus);
  // the bonus keeps its gains only (an older one's single value moves into them)
  const setGains = (next: Gain[]) => {
    const { value: _value, factor: _factor, ...rest } = bonus;
    onChange({ ...rest, gains: next });
  };
  const toggle = (field: "activity" | "media_kind", item: string, on: boolean) => {
    const current = when[field] ?? [];
    onChange({
      ...bonus,
      when: { ...when, [field]: on ? [...current, item] : current.filter((x) => x !== item) },
    });
  };
  return (
    <div className="campaign-bonus">
      <div className="campaign-bonus__head">
        <fieldset className="campaign-gains">
          <legend>{t("campaigns:editor.gains")}</legend>
          {VALUES.map((v) => {
            const gain = gains.find((g) => g.value === v);
            return (
              <div key={v} className="campaign-gain" data-on={gain ? "" : undefined}>
                <CheckboxField
                  label={t(`gamification:value.${v}`)}
                  checked={Boolean(gain)}
                  onChange={(e) =>
                    setGains(
                      e.target.checked
                        ? [...gains, { value: v, factor: 2 }]
                        : gains.filter((g) => g.value !== v),
                    )
                  }
                />
                {gain ? (
                  <span className="campaign-gain__factor">
                    ×
                    <input
                      type="number"
                      min={0.1}
                      max={10}
                      step="0.1"
                      aria-label={t("campaigns:editor.factorOf", { value: t(`gamification:value.${v}`) })}
                      value={String(gain.factor)}
                      onChange={(e) =>
                        setGains(
                          gains.map((g) => (g.value === v ? { ...g, factor: Number(e.target.value) } : g)),
                        )
                      }
                    />
                  </span>
                ) : null}
              </div>
            );
          })}
          {!gains.length ? <p className="admin-muted">{t("campaigns:editor.noGain")}</p> : null}
        </fieldset>
        <Button variant="ghost" size="icon" aria-label={t("campaigns:editor.remove")} onClick={onRemove}>
          <Icon name="trash" size={16} />
        </Button>
      </div>
      <fieldset className="campaign-bonus__group">
        <legend>{t("campaigns:editor.actions")}</legend>
        <div className="campaign-checks">
          {ACTIONS.map((action) => (
            <CheckboxField
              key={action}
              label={t(`gamification:action.${action.replaceAll(".", "_")}`)}
              checked={(when.activity ?? []).includes(action)}
              onChange={(e) => toggle("activity", action, e.target.checked)}
            />
          ))}
        </div>
        <p className="admin-muted">{t("campaigns:editor.actionsHint")}</p>
      </fieldset>
      <fieldset className="campaign-bonus__group">
        <legend>{t("campaigns:editor.kinds")}</legend>
        <div className="campaign-checks">
          {MEDIA_KINDS.map((kind) => (
            <CheckboxField
              key={kind}
              label={t(`media:kind.${kind}`)}
              checked={(when.media_kind ?? []).includes(kind)}
              onChange={(e) => toggle("media_kind", kind, e.target.checked)}
            />
          ))}
        </div>
      </fieldset>
      <FormGrid>
        <TextField
          label={t("campaigns:editor.genres")}
          hint={t("campaigns:editor.genresHint")}
          value={(when.genre ?? []).join(", ")}
          onChange={(e) => onChange({ ...bonus, when: { ...when, genre: list(e.target.value) } })}
        />
        <TextField
          label={t("campaigns:editor.titles")}
          hint={t("campaigns:editor.titlesHint")}
          value={(when.title_contains ?? []).join(", ")}
          onChange={(e) => onChange({ ...bonus, when: { ...when, title_contains: list(e.target.value) } })}
        />
        <TextField
          label={t("campaigns:editor.keywords")}
          hint={t("campaigns:editor.keywordsHint")}
          value={(when.keyword ?? []).join(", ")}
          onChange={(e) => onChange({ ...bonus, when: { ...when, keyword: list(e.target.value) } })}
        />
      </FormGrid>
      <PickedTitles
        ids={when.objects ?? []}
        onChange={(objects) => onChange({ ...bonus, when: { ...when, objects } })}
      />
      <p className="admin-muted">{t("campaigns:editor.themedHint")}</p>
    </div>
  );
}

function DiscountEditor({
  discount,
  onChange,
  onRemove,
}: {
  discount: Discount;
  onChange: (next: Discount) => void;
  onRemove: () => void;
}) {
  const t = useT();
  const shop = useShop();
  const [query, setQuery] = useState("");
  const shown = shop.products
    .filter((p) => p.state !== "archived" && p.price_coins)
    .filter((p) => !query || `${p.name} ${p.key}`.toLowerCase().includes(query.toLowerCase()));
  return (
    <div className="campaign-bonus">
      <div className="campaign-bonus__head">
        <TextField
          label={t("campaigns:editor.percent")}
          type="number"
          min={1}
          max={90}
          value={String(discount.percent)}
          onChange={(e) => onChange({ ...discount, percent: Number(e.target.value) })}
        />
        <Button variant="ghost" size="icon" aria-label={t("campaigns:editor.remove")} onClick={onRemove}>
          <Icon name="trash" size={16} />
        </Button>
      </div>
      <CheckboxField
        label={t("campaigns:editor.everything")}
        hint={t("campaigns:editor.everythingHint")}
        checked={Boolean(discount.everything)}
        onChange={(e) => onChange({ ...discount, everything: e.target.checked })}
      />
      <fieldset className="campaign-bonus__group">
        <legend>{t("campaigns:editor.seasons")}</legend>
        <div className="campaign-checks">
          {SEASONS.map((season) => (
            <CheckboxField
              key={season}
              label={t(`campaigns:editor.season.${season}`)}
              checked={(discount.seasons ?? []).includes(season)}
              onChange={(e) =>
                onChange({
                  ...discount,
                  seasons: e.target.checked
                    ? [...(discount.seasons ?? []), season]
                    : (discount.seasons ?? []).filter((x) => x !== season),
                })
              }
            />
          ))}
        </div>
        <p className="admin-muted">{t("campaigns:editor.seasonsHint")}</p>
      </fieldset>
      <fieldset className="campaign-bonus__group">
        <legend>{t("campaigns:editor.categories")}</legend>
        <div className="campaign-checks">
          {shop.categories.map((category) => (
            <CheckboxField
              key={category.key}
              label={t(category.label_key)}
              checked={discount.categories.includes(category.key)}
              onChange={(e) =>
                onChange({
                  ...discount,
                  categories: e.target.checked
                    ? [...discount.categories, category.key]
                    : discount.categories.filter((c) => c !== category.key),
                })
              }
            />
          ))}
        </div>
      </fieldset>
      <fieldset className="campaign-bonus__group">
        <legend>{t("campaigns:editor.products", { count: discount.products.length })}</legend>
        <SearchBox label={t("campaigns:editor.searchProducts")} value={query} onChange={setQuery} />
        <div className="campaign-checks campaign-checks--products">
          {shown.map((product) => (
            <CheckboxField
              key={product.key}
              label={product.name}
              hint={`${product.price_coins} Coins`}
              checked={discount.products.includes(product.key)}
              onChange={(e) =>
                onChange({
                  ...discount,
                  products: e.target.checked
                    ? [...discount.products, product.key]
                    : discount.products.filter((k) => k !== product.key),
                })
              }
            />
          ))}
        </div>
      </fieldset>
    </div>
  );
}

const local = (value?: string | null) => (value ? value.slice(0, 16) : "");

export function CampaignEditor({ campaign, onDone }: { campaign?: Campaign; onDone: () => void }) {
  const t = useT();
  const admin = useCampaignAdmin();
  const initial = (campaign?.definition as unknown as CampaignDef | undefined) ?? {
    names: { fr: "", en: "" },
    timezone: "Europe/Paris",
    schedule: { start_at: "", end_at: "", recurrence: { kind: "none" } },
    modifiers: [],
    discounts: [],
  };
  const [def, setDef] = useState<CampaignDef>(initial);
  const [key, setKey] = useState(campaign?.key ?? "");
  const [error, setError] = useState<string | null>(null);
  const bonuses = def.modifiers ?? [];
  const discounts = def.discounts ?? [];
  const patch = (next: Partial<CampaignDef>) => setDef({ ...def, ...next });
  const clean = (): Record<string, unknown> => {
    const schedule = { ...def.schedule };
    if (!schedule.end_at) schedule.end_at = null;
    if (schedule.end_at) schedule.duration_hours = null;
    const out: Record<string, unknown> = {
      ...def,
      names: Object.fromEntries(Object.entries(def.names).filter(([, v]) => v.trim())),
      schedule: Object.fromEntries(Object.entries(schedule).filter(([, v]) => v !== null && v !== "")),
      modifiers: bonuses.map((b) => ({
        ...b,
        when: Object.fromEntries(
          Object.entries(b.when).filter(([, v]) => !(Array.isArray(v) && v.length === 0)),
        ),
      })),
      discounts,
    };
    if (!def.ending_soon_hours) delete out.ending_soon_hours;
    return out;
  };
  const fail = (failure: unknown) => {
    const errors =
      failure instanceof ApiError ? (failure.extensions.errors as string[] | undefined) : undefined;
    setError(
      failure instanceof ApiError ? [failure.message, ...(errors ?? [])].join(" — ") : String(failure),
    );
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    const definition = clean();
    try {
      if (!campaign) await admin.create.mutateAsync({ key, definition });
      else {
        try {
          await admin.publish.mutateAsync({ id: campaign.id, definition });
        } catch (failure) {
          if (failure instanceof ApiError && failure.code === "authz.confirmation_required") {
            if (!window.confirm(t("campaigns:admin.confirm"))) return;
            await admin.publish.mutateAsync({
              id: campaign.id,
              definition,
              confirmation: String(failure.extensions.confirmation ?? ""),
            });
          } else throw failure;
        }
      }
      onDone();
    } catch (failure) {
      fail(failure);
    }
  };
  return (
    <form className="admin-form campaign-editor" onSubmit={(event) => void submit(event)}>
      <FormGrid>
        <TextField
          label={t("campaigns:editor.nameFr")}
          required
          maxLength={120}
          value={def.names.fr ?? ""}
          onChange={(e) => {
            patch({ names: { ...def.names, fr: e.target.value } });
            if (!campaign)
              setKey(
                e.target.value
                  .normalize("NFKD")
                  .replace(/[^\w\s-]/g, "")
                  .trim()
                  .toLowerCase()
                  .replace(/[\s-]+/g, "_")
                  .slice(0, 60),
              );
          }}
        />
        <TextField
          label={t("campaigns:editor.nameEn")}
          maxLength={120}
          value={def.names.en ?? ""}
          onChange={(e) => patch({ names: { ...def.names, en: e.target.value } })}
        />
        {!campaign ? (
          <TextField
            label={t("campaigns:admin.key")}
            required
            pattern="^[a-z0-9][a-z0-9_\-]{1,63}$"
            value={key}
            onChange={(e) => setKey(e.target.value)}
          />
        ) : null}
      </FormGrid>
      <TextField
        label={t("campaigns:editor.description")}
        maxLength={2000}
        value={def.description ?? ""}
        onChange={(e) => patch({ description: e.target.value })}
      />
      <fieldset className="gam-fieldset">
        <legend>{t("campaigns:editor.when")}</legend>
        <FormGrid>
          <TextField
            label={t("campaigns:editor.start")}
            type="datetime-local"
            required
            value={local(def.schedule.start_at)}
            onChange={(e) => patch({ schedule: { ...def.schedule, start_at: `${e.target.value}:00` } })}
          />
          <TextField
            label={t("campaigns:editor.end")}
            type="datetime-local"
            required
            value={local(def.schedule.end_at)}
            onChange={(e) => patch({ schedule: { ...def.schedule, end_at: `${e.target.value}:00` } })}
          />
          <SelectField
            label={t("campaigns:editor.repeat")}
            value={def.schedule.recurrence?.kind === "yearly" ? "yearly" : "none"}
            onChange={(e) =>
              patch({
                schedule: { ...def.schedule, recurrence: { kind: e.target.value as "none" | "yearly" } },
              })
            }
          >
            <option value="none">{t("campaigns:editor.once")}</option>
            <option value="yearly">{t("campaigns:editor.yearly")}</option>
          </SelectField>
          <TextField
            label={t("campaigns:editor.timezone")}
            value={def.timezone ?? "UTC"}
            onChange={(e) => patch({ timezone: e.target.value })}
          />
        </FormGrid>
      </fieldset>
      <fieldset className="gam-fieldset">
        <legend>{t("campaigns:editor.bonuses")}</legend>
        <p className="admin-muted">{t("campaigns:editor.bonusesHint")}</p>
        {bonuses.map((bonus, index) => (
          <BonusEditor
            key={bonus.id}
            bonus={bonus}
            onChange={(next) => patch({ modifiers: bonuses.map((b, i) => (i === index ? next : b)) })}
            onRemove={() => patch({ modifiers: bonuses.filter((_, i) => i !== index) })}
          />
        ))}
        <Button
          variant="secondary"
          onClick={() => {
            let index = bonuses.length;
            while (bonuses.some((b) => b.id === blankBonus(index).id)) index += 1;
            patch({ modifiers: [...bonuses, blankBonus(index)] });
          }}
        >
          <Icon name="plus" size={16} />
          {t("campaigns:editor.addBonus")}
        </Button>
      </fieldset>
      <fieldset className="gam-fieldset">
        <legend>{t("campaigns:editor.discounts")}</legend>
        <p className="admin-muted">{t("campaigns:editor.discountsHint")}</p>
        {discounts.map((discount, index) => (
          <DiscountEditor
            key={discount.id}
            discount={discount}
            onChange={(next) => patch({ discounts: discounts.map((d, i) => (i === index ? next : d)) })}
            onRemove={() => patch({ discounts: discounts.filter((_, i) => i !== index) })}
          />
        ))}
        <Button
          variant="secondary"
          onClick={() => {
            let index = discounts.length + 1;
            while (discounts.some((d) => d.id === `discount_${index}`)) index += 1;
            patch({
              discounts: [
                ...discounts,
                { id: `discount_${index}`, percent: 20, products: [], categories: [] },
              ],
            });
          }}
        >
          <Icon name="plus" size={16} />
          {t("campaigns:editor.addDiscount")}
        </Button>
      </fieldset>
      {error ? (
        <p role="alert" className="services-admin__ko">
          {error}
        </p>
      ) : null}
      <FormActions>
        <Button type="submit" disabled={!key || admin.create.isPending || admin.publish.isPending}>
          <Icon name="check" size={16} />
          {campaign ? t("campaigns:admin.publish") : t("campaigns:admin.save")}
        </Button>
      </FormActions>
    </form>
  );
}
