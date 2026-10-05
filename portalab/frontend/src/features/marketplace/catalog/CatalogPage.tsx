import { useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { CoinBadge } from "../../../design-system/components/Badges";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { EmptyState, Skeleton } from "../../../design-system/components/Placeholders";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { PROGRESSION_KEY } from "../../../shell/header/useHeaderData";
import type { Progression } from "../../gamification/api";
import { type Category, type Product, useCategories, useDescribe, useProducts } from "../api";
import { ProductArt } from "./ProductArt";
import { ProductCard } from "./ProductCard";
import { ProductModal } from "./ProductModal";
import "../marketplace.css";

/**
 * ``/marketplace`` (spec 015 T021, 027 US8): a game-style shop — featured banner, shelves by collection or
 * by type, rarity filter and search; a product opens in a modal with its preview (027). Products are bought with Coins earned on the portal, never real money.
 */
export const TYPE_GROUPS: Array<{ key: string; icon: string; types: string[] }> = [
  { key: "badges", icon: "star", types: ["badge", "title"] },
  { key: "animations", icon: "sparkles", types: ["effect", "ambient"] },
  { key: "themes", icon: "palette", types: ["theme", "palette"] },
  {
    key: "profile",
    icon: "user",
    types: ["profile_banner", "avatar_frame", "profile_backdrop", "profile_background", "name_style"],
  },
  { key: "notifications", icon: "bell", types: ["notification_style", "notification_animation"] },
  { key: "packs", icon: "shop", types: ["bundle"] },
  { key: "features", icon: "zap", types: ["feature", "plugin", "widget", "statistic", "access"] },
  { key: "bonus", icon: "inbox", types: ["quota"] },
];
const RARITIES = ["common", "rare", "epic", "legendary"] as const;
const RANK: Record<string, number> = { legendary: 0, epic: 1, rare: 2, common: 3 };

function groupOf(type: string): string {
  return TYPE_GROUPS.find((g) => g.types.includes(type))?.key ?? "other";
}

function byRarity(a: Product, b: Product): number {
  return (
    (RANK[a.rarity ?? "common"] ?? 3) - (RANK[b.rarity ?? "common"] ?? 3) || a.name.localeCompare(b.name)
  );
}

export default function CatalogPage() {
  const t = useT();
  const client = useQueryClient();
  const coins = client.getQueryData<Progression>(PROGRESSION_KEY)?.coins;
  const [view, setView] = useState<"collections" | "types">("collections");
  const [rarity, setRarity] = useState("");
  const [q, setQ] = useState("");
  const [params, setParams] = useSearchParams();
  const type = params.get("type") ?? ""; // 027: « in the shop » links land on one type
  const [opened, setOpened] = useState<Product | null>(null);
  const describe = useDescribe();
  const categories = useCategories();
  const products = useProducts({ category: "", q: q.trim() });
  const all = useMemo(
    () =>
      (products.data ?? [])
        .filter((p) => (!rarity || p.rarity === rarity) && (!type || p.type === type))
        .sort(byRarity),
    [products.data, rarity, type],
  );
  const featured = all.filter((p) => p.featured);
  const shelves = useMemo(() => {
    if (view === "types") {
      return [
        ...TYPE_GROUPS.map((g) => ({ key: g.key, icon: g.icon, title: t(`marketplace:group.${g.key}`) })),
        { key: "other", icon: "more", title: t("marketplace:group.other") },
      ]
        .map((g) => ({ ...g, items: all.filter((p) => groupOf(p.type) === g.key) }))
        .filter((g) => g.items.length);
    }
    const known = (categories.data ?? []) as Category[];
    return [
      ...known.map((c) => ({
        key: c.key,
        icon: c.icon ?? "star",
        title: t(c.label_key),
        items: all.filter((p) => p.category === c.key),
      })),
      {
        key: "_other",
        icon: "more",
        title: t("marketplace:shop.otherCollection"),
        items: all.filter((p) => !p.category || !known.some((c) => c.key === p.category)),
      },
    ].filter((g) => g.items.length);
  }, [view, all, categories.data, t]);

  return (
    <div className="shop">
      <PageHeader
        icon="shop"
        title={t("marketplace:catalog.title")}
        context={t("marketplace:catalog.intro")}
        secondary={
          <>
            {coins !== undefined ? <CoinBadge amount={coins} label={t("gamification:value.coins")} /> : null}
            <Link className="ds-button ds-button--secondary" to="/projects">
              {t("marketplace:shop.projects")}
            </Link>
            <Link className="ds-button ds-button--primary" to="/marketplace/owned">
              <Icon name="star" size={18} />
              {t("marketplace:shop.myItems")}
            </Link>
          </>
        }
      />

      {type ? (
        <p className="shop-type-filter">
          <Icon name="list" size={16} />
          {t(`marketplace:type.${type}`)}
          <Button variant="ghost" onClick={() => setParams({})}>
            <Icon name="close" size={14} />
            {t("marketplace:shop.allTypes")}
          </Button>
        </p>
      ) : null}

      {featured.length && !q && !rarity && !type ? (
        <section className="shop-featured" aria-labelledby="shop-featured">
          <h2 id="shop-featured" className="shop-shelf__title">
            <Icon name="sparkles" size={20} /> {t("marketplace:shop.featured")}
          </h2>
          <ul className="shop-featured__list">
            {featured.map((product) => (
              <li key={product.key} className="shop-hero" data-rarity={product.rarity ?? "common"}>
                <ProductArt product={product} />
                <div className="shop-hero__text">
                  <span className="product-card__rarity">
                    {t(`marketplace:rarity.${product.rarity ?? "common"}`)}
                  </span>
                  <h3>
                    <Link
                      to={`/marketplace/products/${product.key}`}
                      onClick={(event) => {
                        if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
                        event.preventDefault();
                        setOpened(product);
                      }}
                    >
                      {product.name}
                    </Link>
                  </h3>
                  {describe(product) ? <p>{describe(product)}</p> : null}
                  {product.owned ? (
                    <span className="product-card__owned">
                      <Icon name="check" size={16} /> {t("marketplace:product.owned")}
                    </span>
                  ) : product.price_coins ? (
                    <CoinBadge amount={product.price_coins} label={t("gamification:value.coins")} />
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="shop-toolbar">
        <fieldset className="ds-subnav" aria-label={t("marketplace:catalog.title")}>
          <button type="button" aria-pressed={view === "collections"} onClick={() => setView("collections")}>
            <Icon name="star" size={16} /> {t("marketplace:shop.byCollection")}
          </button>
          <button type="button" aria-pressed={view === "types"} onClick={() => setView("types")}>
            <Icon name="list" size={16} /> {t("marketplace:shop.byType")}
          </button>
        </fieldset>
        <fieldset className="shop-rarities" aria-label={t("marketplace:shop.rarity")}>
          <button type="button" aria-pressed={!rarity} onClick={() => setRarity("")}>
            {t("marketplace:shop.allRarities")}
          </button>
          {RARITIES.map((r) => (
            <button
              key={r}
              type="button"
              data-rarity={r}
              aria-pressed={rarity === r}
              onClick={() => setRarity(rarity === r ? "" : r)}
            >
              {t(`marketplace:rarity.${r}`)}
            </button>
          ))}
        </fieldset>
        <label className="shop-search">
          <Icon name="search" size={18} />
          <span className="visually-hidden">{t("marketplace:catalog.search")}</span>
          <input
            type="search"
            value={q}
            maxLength={64}
            placeholder={t("marketplace:catalog.search")}
            onChange={(e) => setQ(e.target.value)}
          />
        </label>
      </div>

      {products.isPending ? <Skeleton shape="tile" count={6} label={t("marketplace:catalog.title")} /> : null}
      {products.isError ? <FunctionalState state="unavailable" onRetry={() => products.refetch()} /> : null}
      {products.data && all.length === 0 ? (
        <EmptyState
          icon="shop"
          title={t("marketplace:shop.nothing")}
          action={
            <Button
              variant="secondary"
              onClick={() => {
                setQ("");
                setRarity("");
              }}
            >
              {t("marketplace:shop.reset")}
            </Button>
          }
        />
      ) : null}
      {shelves.map((shelf) => (
        <section key={shelf.key} className="shop-shelf" aria-labelledby={`shelf-${shelf.key}`}>
          <h2 id={`shelf-${shelf.key}`} className="shop-shelf__title">
            <Icon name={shelf.icon} size={20} /> {shelf.title}
            <span className="shop-shelf__count">{shelf.items.length}</span>
          </h2>
          <ul className="shop-shelf__list">
            {shelf.items.map((product) => (
              <ProductCard key={product.key} product={product} onOpen={setOpened} />
            ))}
          </ul>
        </section>
      ))}
      {opened ? <ProductModal product={opened} onClose={() => setOpened(null)} /> : null}
    </div>
  );
}
