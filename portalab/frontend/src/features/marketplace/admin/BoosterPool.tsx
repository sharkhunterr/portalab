import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../../api/client";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";
import type { Product } from "../api";
import { localized } from "../boosters/api";
import { RARITIES } from "./ProductEditor";

/**
 * The owner (2026-10-19): every booster says exactly what it may draw — visual packs (a pack's catalogue,
 * Portalab's or imported), the shop's packs, and items named one by one — and the administrators see, as
 * they choose, what that makes: how many looks per rarity, and the items named that it can never draw.
 */

// the kinds a booster may draw (the server's own lists: the looks, the reserve's items)
const LOOKS = new Set([
  "ambient",
  "avatar_frame",
  "profile_banner",
  "profile_background",
  "name_style",
  "level_badge",
  "level_up",
  "badge",
  "title",
  "notification_style",
  "notification_animation",
  "effect",
  "palette",
]);
const RESERVE = new Set([
  "quota",
  "streak_freeze",
  "xp_boost",
  "media_rescue",
  "special_request",
  "project_launch",
]);
const VISUAL = "visual:";
const SHOWN = 40;

export interface PoolDraft {
  pool: string;
  visualPacks: string[];
  shopPacks: string[];
  items: string[];
}

export interface PoolPreview {
  count: number;
  rarities: Record<string, number>;
  types: Record<string, number>;
  items: Array<{ key: string; type: string; rarity: string; names: Record<string, string> }>;
  not_drawable: string[];
}

export const poolPacks = (draft: PoolDraft) => [
  ...draft.shopPacks,
  ...draft.visualPacks.map((p) => `${VISUAL}${p}`),
];

export const poolNamed = (draft: PoolDraft) => draft.items.length > 0 || poolPacks(draft).length > 0;

/** What a booster naming these packs and items would draw now (the server's own rules). */
export function usePoolPreview(draft: PoolDraft | null) {
  const body = draft ? { pool: draft.pool, packs: poolPacks(draft), items: draft.items } : null;
  return useQuery({
    queryKey: ["marketplace", "booster-pool", body],
    enabled: body !== null,
    staleTime: 30_000,
    queryFn: async () =>
      (
        await api.POST("/api/v1/admin/marketplace/boosters/pool", {
          body: body as never,
        })
      ).data as unknown as PoolPreview,
  });
}

/** One line telling what the pool holds: how many, per rarity. */
export function PoolSummary({
  preview,
  odds,
}: {
  preview: PoolPreview | undefined;
  odds?: Record<string, string>;
}) {
  const t = useT();
  const format = useFormat();
  if (!preview) return null;
  if (!preview.count)
    return (
      <p className="admin-booster__pool-summary" data-empty="true" role="status">
        <Icon name="warning" size={16} /> {t("marketplace:admin.boosters.poolEmpty")}
      </p>
    );
  // a rarity it may roll (its weight above 0) but holds none of: the draw falls back to the nearest below
  const missing = RARITIES.filter((r) => Number(odds?.[r] ?? 0) > 0 && !preview.rarities[r]);
  return (
    <p className="admin-booster__pool-summary" role="status">
      <strong>{t("marketplace:admin.boosters.poolCount", { count: preview.count })}</strong>
      {RARITIES.map((r) => (
        <span key={r} data-rarity={r}>
          {t(`marketplace:rarity.${r}`)} {format.number(preview.rarities[r] ?? 0)}
        </span>
      ))}
      {missing.length ? (
        <span className="admin-booster__pool-missing">
          <Icon name="warning" size={14} />{" "}
          {t("marketplace:admin.boosters.poolMissing", {
            rarities: missing.map((r) => t(`marketplace:rarity.${r}`)).join(", "),
          })}
        </span>
      ) : null}
    </p>
  );
}

/** A list of checkboxes one can narrow by a few letters (there are many packs). */
function Ticks({
  legend,
  hint,
  entries,
  ticked,
  onChange,
}: {
  legend: string;
  hint: string;
  entries: Array<{ id: string; label: string }>;
  ticked: string[];
  onChange: (next: string[]) => void;
}) {
  const t = useT();
  const [filter, setFilter] = useState("");
  const words = filter.trim().toLowerCase();
  // the ones ticked first (what it draws now), then the others the filter keeps
  const shown = [
    ...entries.filter((e) => ticked.includes(e.id)),
    ...entries.filter(
      (e) => !ticked.includes(e.id) && (!words || `${e.label} ${e.id}`.toLowerCase().includes(words)),
    ),
  ];
  return (
    <fieldset className="admin-booster__packs">
      <legend>
        {legend} · {t("marketplace:admin.boosters.ticked", { count: ticked.length })}
      </legend>
      <p className="admin-muted">{hint}</p>
      <TextField
        label={t("marketplace:admin.boosters.filter")}
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />
      <div className="admin-booster__ticks">
        {shown.map((entry) => (
          <CheckboxField
            key={entry.id}
            label={entry.label}
            checked={ticked.includes(entry.id)}
            onChange={(e) =>
              onChange(e.target.checked ? [...ticked, entry.id] : ticked.filter((p) => p !== entry.id))
            }
          />
        ))}
      </div>
    </fieldset>
  );
}

/** The booster's pool: its visual packs, the shop's packs and its items, and what that makes. */
export function PoolPicker({
  value,
  patch,
  visualPacks,
  products,
  odds,
}: {
  value: PoolDraft;
  patch: (next: Partial<PoolDraft>) => void;
  visualPacks: Array<{ id: string; names: Record<string, string>; products: number }>;
  products: readonly Product[];
  odds: Record<string, string>;
}) {
  const t = useT();
  const { locale } = useLocaleContext();
  const [search, setSearch] = useState("");
  const preview = usePoolPreview(value);
  const kinds = value.pool === "reserve" ? RESERVE : LOOKS;
  const named = (p: Product) => p.name || localized(p.names ?? {}, locale) || p.key;
  const byKey = new Map(products.map((p) => [p.key, p]));
  const bundles = products
    .filter((p) => p.type === "bundle" && p.state === "available")
    .map((p) => {
      const inside = ((p.preview ?? {}) as { products?: string[] }).products?.length ?? 0;
      return {
        id: p.key,
        label: `${named(p)} · ${t("marketplace:admin.boosters.packCount", { count: inside })}`,
      };
    });
  const words = search.trim().toLowerCase();
  const candidates = words
    ? products
        .filter(
          (p) =>
            kinds.has(p.type) &&
            p.state === "available" &&
            (p.price_coins ?? 0) > 0 &&
            !value.items.includes(p.key) &&
            `${named(p)} ${p.key}`.toLowerCase().includes(words),
        )
        .slice(0, SHOWN)
    : [];
  const notDrawable = new Set(preview.data?.not_drawable ?? []);
  return (
    <div className="admin-booster__pool">
      <PoolSummary preview={preview.data} odds={odds} />
      {value.pool === "reserve" ? null : (
        <>
          <Ticks
            legend={t("marketplace:admin.boosters.packs")}
            hint={t("marketplace:admin.boosters.packsHint")}
            entries={visualPacks.map((pack) => ({
              id: pack.id,
              label: `${localized(pack.names, locale) || pack.id} · ${t(
                "marketplace:admin.boosters.packCount",
                {
                  count: pack.products,
                },
              )}`,
            }))}
            ticked={value.visualPacks}
            onChange={(visualPacks) => patch({ visualPacks })}
          />
          <Ticks
            legend={t("marketplace:admin.boosters.shopPacks")}
            hint={t("marketplace:admin.boosters.shopPacksHint")}
            entries={bundles}
            ticked={value.shopPacks}
            onChange={(shopPacks) => patch({ shopPacks })}
          />
        </>
      )}
      <fieldset className="admin-booster__packs">
        <legend>
          {t("marketplace:admin.boosters.items")} ·{" "}
          {t("marketplace:admin.boosters.ticked", { count: value.items.length })}
        </legend>
        <p className="admin-muted">{t("marketplace:admin.boosters.itemsHint")}</p>
        {value.items.length ? (
          <ul className="admin-booster__chips">
            {value.items.map((itemKey) => {
              const product = byKey.get(itemKey);
              return (
                <li
                  key={itemKey}
                  data-rarity={product?.rarity ?? "common"}
                  data-lost={notDrawable.has(itemKey) || undefined}
                >
                  {product ? named(product) : itemKey}
                  {notDrawable.has(itemKey) ? (
                    <span className="admin-muted"> · {t("marketplace:admin.boosters.notDrawable")}</span>
                  ) : null}
                  <Button
                    variant="ghost"
                    aria-label={t("marketplace:admin.boosters.removeItem", {
                      name: product ? named(product) : itemKey,
                    })}
                    onClick={() => patch({ items: value.items.filter((k) => k !== itemKey) })}
                  >
                    <Icon name="close" size={14} />
                  </Button>
                </li>
              );
            })}
          </ul>
        ) : null}
        <TextField
          label={t("marketplace:admin.boosters.itemsSearch")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {candidates.length ? (
          <ul className="admin-booster__candidates">
            {candidates.map((p) => (
              <li key={p.key} data-rarity={p.rarity ?? "common"}>
                <Button variant="secondary" onClick={() => patch({ items: [...value.items, p.key] })}>
                  <Icon name="plus" size={14} /> {named(p)}
                </Button>
                <span className="admin-muted">
                  {t(`marketplace:type.${p.type}`)} · {t(`marketplace:rarity.${p.rarity ?? "common"}`)}
                </span>
              </li>
            ))}
          </ul>
        ) : words ? (
          <p className="admin-muted">{t("marketplace:admin.boosters.itemsNone")}</p>
        ) : null}
      </fieldset>
    </div>
  );
}
