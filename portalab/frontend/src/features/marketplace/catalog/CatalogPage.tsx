import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { EmptyState, Skeleton } from "../../../design-system/components/Placeholders";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { useProgression } from "../../gamification/api";
import { BoostTag } from "../../gamification/boost";
import { type Product, useDescribe, useProducts } from "../api";
import { BoosterHistory } from "../boosters/Boosters";
import { LazyArt } from "./LazyArt";
import { Price, priceOf } from "./Price";
import { ProductCard } from "./ProductCard";
import { ProductModal } from "./ProductModal";
import "../marketplace.css";
import { productTypeLabel } from "../typeLabel";

/**
 * ``/marketplace`` (spec 015 T021, 027 US8): a shop in departments — themes (theme packs, interfaces,
 * palettes), profile (banners, frames, backgrounds, names, badges, titles, level badges), notifications
 * and effects, features (widgets and their settings, statistics, bonuses, project launches) and packs —
 * each a shelf per kind, the first items shown and « see all » for the rest; art is drawn when a card
 * comes near the screen. A product opens in a modal. Bought with Coins earned on the portal, never real
 * money.
 */
export interface Shelf {
  key: string;
  icon: string;
  types: string[];
  /** Only the products of this collection (theme packs among the packs), or all but it. */
  category?: string;
  notCategory?: string;
}

export const DEPARTMENTS: Array<{ key: string; icon: string; shelves: Shelf[] }> = [
  {
    key: "themes",
    icon: "palette",
    shelves: [
      // a theme pack is the whole theme; an interface is the theme's look of the portal only
      { key: "themePacks", icon: "crown", types: ["bundle"], category: "ultimate" },
      { key: "interfaces", icon: "palette", types: ["theme"] },
      { key: "palettes", icon: "palette", types: ["palette"] },
    ],
  },
  {
    key: "profile",
    icon: "user",
    shelves: [
      { key: "banners", icon: "image", types: ["profile_banner", "profile_backdrop"] },
      { key: "frames", icon: "user", types: ["avatar_frame"] },
      { key: "backgrounds", icon: "sparkles", types: ["profile_background"] },
      { key: "names", icon: "feather", types: ["name_style"] },
      { key: "badges", icon: "star", types: ["badge"] },
      { key: "titles", icon: "award", types: ["title"] },
      { key: "levelBadges", icon: "trophy", types: ["level_badge"] },
    ],
  },
  {
    key: "effects",
    icon: "sparkles",
    shelves: [
      { key: "notificationStyles", icon: "bell", types: ["notification_style"] },
      { key: "notificationAnimations", icon: "bell-ring", types: ["notification_animation"] },
      { key: "ambients", icon: "snowflake", types: ["ambient"] },
      { key: "celebrations", icon: "party", types: ["effect"] },
      { key: "levelUps", icon: "trophy", types: ["level_up"] },
    ],
  },
  {
    key: "features",
    icon: "zap",
    shelves: [
      { key: "widgets", icon: "dashboard", types: ["widget"] },
      { key: "widgetOptions", icon: "settings", types: ["widget_option"] },
      { key: "statistics", icon: "chart", types: ["statistic"] },
      { key: "services", icon: "server", types: ["service_access"] }, // 027: a homelab service's access
      { key: "requests", icon: "clapperboard", types: ["special_request"] }, // 027: a film in 4K…
      { key: "community", icon: "lightbulb", types: ["project_launch"] },
      { key: "perks", icon: "rocket", types: ["xp_boost", "streak_freeze", "media_rescue"] }, // #54/#55/#57
      { key: "bonus", icon: "inbox", types: ["quota", "feature", "plugin", "access"] },
    ],
  },
  {
    key: "packs",
    icon: "shop",
    shelves: [{ key: "packs", icon: "shop", types: ["bundle"], notCategory: "ultimate" }],
  },
  // #81: sealed packs drawn at random — products like the others (a tile, a sheet), the season's first
  { key: "boosters", icon: "sparkles", shelves: [{ key: "boosters", icon: "sparkles", types: ["booster"] }] },
];
const RARITIES = ["common", "rare", "epic", "legendary"] as const;
const RANK: Record<string, number> = { legendary: 0, epic: 1, rare: 2, common: 3 };
const FIRST = 8; // shown per shelf before « see all »

function onShelf(shelf: Shelf, product: Product): boolean {
  return (
    shelf.types.includes(product.type) &&
    (!shelf.category || product.category === shelf.category) &&
    (!shelf.notCategory || product.category !== shelf.notCategory)
  );
}

/** The department a kind of product is in (an « in the shop » link lands on one type). */
export function departmentOf(type: string): string {
  return DEPARTMENTS.find((d) => d.shelves.some((s) => s.types.includes(type)))?.key ?? "features";
}

/** The department a product is on (theme packs and other packs part ways). */
export function departmentOfProduct(product: Product): string {
  return DEPARTMENTS.find((d) => d.shelves.some((s) => onShelf(s, product)))?.key ?? "features";
}

/** Shelf order (027): what is for sale first (sold out last, still shown), featured first, then from the
 * most affordable — rarity is not the order, so a shelf is not a wall of legendaries. */
function shelfOrder(a: Product, b: Product): number {
  const soldOut = (p: Product) => (p.remaining === 0 && !p.owned ? 1 : 0);
  return (
    soldOut(a) - soldOut(b) ||
    Number(b.featured) - Number(a.featured) ||
    (priceOf(a) ?? 0) - (priceOf(b) ?? 0) ||
    (RANK[a.rarity ?? "common"] ?? 3) - (RANK[b.rarity ?? "common"] ?? 3) ||
    a.name.localeCompare(b.name)
  );
}

/** #54/#55: on the perks' shelf, the boost in progress (bought now, the next one starts after it). */
function PerksNow() {
  const boost = useProgression().data?.boost;
  return boost ? <BoostTag boost={boost} /> : null;
}

function ShelfView({
  shelf,
  items,
  onOpen,
}: {
  shelf: Shelf;
  items: Product[];
  onOpen: (product: Product) => void;
}) {
  const t = useT();
  const [all, setAll] = useState(false);
  const shown = all ? items : items.slice(0, FIRST);
  return (
    <section className="shop-shelf" aria-labelledby={`shelf-${shelf.key}`}>
      <h2 id={`shelf-${shelf.key}`} className="shop-shelf__title">
        <Icon name={shelf.icon} size={20} /> {t(`marketplace:shelf.${shelf.key}`)}
        <span className="shop-shelf__count">{items.length}</span>
        {shelf.key === "perks" ? <PerksNow /> : null}
        {items.length > FIRST ? (
          <Button variant="ghost" className="shop-shelf__more" onClick={() => setAll(!all)}>
            {all ? t("marketplace:shop.less") : t("marketplace:shop.seeAll", { count: items.length })}
          </Button>
        ) : null}
      </h2>
      <ul className="shop-shelf__list" data-all={all || undefined}>
        {shown.map((product) => (
          <ProductCard key={product.key} product={product} onOpen={onOpen} />
        ))}
      </ul>
    </section>
  );
}

export default function CatalogPage() {
  const t = useT();
  const describe = useDescribe();
  const [params, setParams] = useSearchParams();
  const type = params.get("type") ?? ""; // « in the shop » links land on one type
  const department = params.get("department") ?? (type ? departmentOf(type) : "themes");
  const [rarity, setRarity] = useState("");
  const [q, setQ] = useState("");
  const [opened, setOpened] = useState<Product | null>(null);
  const products = useProducts({ category: "", q: q.trim() });
  const current =
    DEPARTMENTS.find((d) => d.key === department) ?? (DEPARTMENTS[0] as (typeof DEPARTMENTS)[0]);
  const all = useMemo(
    () =>
      (products.data ?? [])
        .filter((p) => (!rarity || p.rarity === rarity) && (!type || p.type === type))
        .sort(shelfOrder),
    [products.data, rarity, type],
  );
  const inDepartment = all.filter((p) => departmentOfProduct(p) === current.key);
  const featured = inDepartment.filter((p) => p.featured).slice(0, 3);
  const counts = Object.fromEntries(
    DEPARTMENTS.map((d) => [d.key, all.filter((p) => departmentOfProduct(p) === d.key).length]),
  );
  const go = (key: string) => setParams(key === "themes" ? {} : { department: key });
  const wanted = params.get("product"); // a product sheet opened from elsewhere (the shop window widget)
  useEffect(() => {
    if (!wanted || !products.data) return;
    const found = products.data.find((p) => p.key === wanted);
    if (found) setOpened(found);
    setParams(found ? { department: departmentOfProduct(found) } : {}, { replace: true });
  }, [wanted, products.data, setParams]);

  return (
    <div className="shop">
      <PageHeader
        icon="shop"
        title={t("marketplace:catalog.title")}
        context={t("marketplace:catalog.intro")}
      />

      <nav className="shop-departments" aria-label={t("marketplace:shop.departments")}>
        {DEPARTMENTS.map((d) => (
          <button
            key={d.key}
            type="button"
            className="shop-department"
            aria-pressed={d.key === current.key}
            onClick={() => go(d.key)}
          >
            <Icon name={d.icon} size={22} />
            <span className="shop-department__text">
              <strong>{t(`marketplace:department.${d.key}`)}</strong>
              <span>{t(`marketplace:department.${d.key}Hint`)}</span>
            </span>
            <span className="shop-department__count">{counts[d.key] ?? 0}</span>
          </button>
        ))}
      </nav>

      <div className="shop-toolbar">
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

      {type ? (
        <p className="shop-type-filter">
          <Icon name="list" size={16} />
          {productTypeLabel(t, type)}
          <Button variant="ghost" onClick={() => setParams({ department: current.key })}>
            <Icon name="close" size={14} />
            {t("marketplace:shop.allTypes")}
          </Button>
        </p>
      ) : null}

      {featured.length && !q && !rarity && !type ? (
        <ul className="shop-featured__list" aria-label={t("marketplace:shop.featured")}>
          {featured.map((product) => (
            <li key={product.key} className="shop-hero" data-rarity={product.rarity ?? "common"}>
              <LazyArt product={product} />
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
                {product.owned && !product.repeatable ? (
                  <span className="product-card__owned">
                    <Icon name="check" size={16} /> {t("marketplace:product.owned")}
                  </span>
                ) : product.price_coins ? (
                  <Price product={product} />
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      {products.isPending ? <Skeleton shape="tile" count={6} label={t("marketplace:catalog.title")} /> : null}
      {products.isError ? <FunctionalState state="unavailable" onRetry={() => products.refetch()} /> : null}
      {products.data && inDepartment.length === 0 ? (
        <EmptyState
          icon="shop"
          title={t("marketplace:shop.nothing")}
          action={
            <Button
              variant="secondary"
              onClick={() => {
                setQ("");
                setRarity("");
                setParams({ department: current.key });
              }}
            >
              {t("marketplace:shop.reset")}
            </Button>
          }
        />
      ) : null}
      {current.shelves.map((shelf) => {
        const items = inDepartment.filter((p) => onShelf(shelf, p));
        return items.length ? (
          <ShelfView key={shelf.key} shelf={shelf} items={items} onOpen={setOpened} />
        ) : null;
      })}
      {current.key === "boosters" ? <BoosterHistory /> : null}
      {opened ? <ProductModal product={opened} onClose={() => setOpened(null)} /> : null}
    </div>
  );
}
