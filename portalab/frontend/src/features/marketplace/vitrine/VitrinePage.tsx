import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { CoinBadge } from "../../../design-system/components/Badges";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { Drawer } from "../../../design-system/components/Overlays";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { EmptyState, Skeleton } from "../../../design-system/components/Placeholders";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { useProgression } from "../../gamification/api";
import { type Product, useDescribe, useProduct, useProducts } from "../api";
import { BOOSTER_EVENT } from "../boosters/api";
import {
  DEPARTMENTS,
  type Department,
  departmentOfProduct,
  type Shelf,
  shelfLabel,
  usePluginShelves,
  withPluginShelves,
} from "../catalog/CatalogPage";
import { LazyArt } from "../catalog/LazyArt";
import { Price, priceOf } from "../catalog/Price";
import { useEquipment } from "../equip";
import { ProductSheet, PurchaseBar, TryOn } from "../product/ProductSheet";
import { productTypeLabel } from "../typeLabel";
import "../marketplace.css";
import "./vitrine.css";

/**
 * ``/marketplace/vitrine`` — a TRIAL of another way through the shop, beside the classic one (which stays as
 * it is): a rail of departments and their shelves with the member's balance, a spotlight of the featured
 * products, picks made for the member (within reach, on sale, nearly sold out, boosters, free), a grid that
 * sorts and filters, and a product opened in a side panel so the browsing stays in view.
 *
 * To remove the trial: delete this folder, the « vitrine » route in ``shell/router/routes.tsx``, the
 * « Try the showcase » button in ``catalog/CatalogPage.tsx`` and the ``vitrine.*`` keys of the
 * ``marketplace`` locales.
 */

const RARITIES = ["common", "rare", "epic", "legendary"] as const;
const RANK: Record<string, number> = { legendary: 0, epic: 1, rare: 2, common: 3 };
const SORTS = ["recommended", "priceAsc", "priceDesc", "rarity", "name"] as const;
const ONLY = ["afford", "unowned", "deal"] as const;
const PAGE = 24;
const RAIL = 12;

type Pick = "afford" | "deal" | "soon" | "boosters" | "free";

const owned = (p: Product) => Boolean(p.owned && !p.repeatable);
const soldOut = (p: Product) => p.remaining === 0 && !owned(p);
const price = (p: Product) => priceOf(p) ?? 0;

function onShelf(shelf: Shelf, product: Product): boolean {
  return (
    shelf.types.includes(product.type) &&
    (!shelf.category || product.category === shelf.category) &&
    (!shelf.notCategory || product.category !== shelf.notCategory)
  );
}

const ORDER: Record<(typeof SORTS)[number], (a: Product, b: Product) => number> = {
  recommended: (a, b) =>
    Number(soldOut(a)) - Number(soldOut(b)) ||
    Number(b.featured) - Number(a.featured) ||
    Number(Boolean(b.discount)) - Number(Boolean(a.discount)) ||
    price(a) - price(b),
  priceAsc: (a, b) => price(a) - price(b),
  priceDesc: (a, b) => price(b) - price(a),
  rarity: (a, b) => (RANK[a.rarity] ?? 3) - (RANK[b.rarity] ?? 3) || price(b) - price(a),
  name: (a, b) => a.name.localeCompare(b.name),
};

/** The picks made for the member: each a rule over the shop. */
function picks(coins: number): Record<Pick, (p: Product) => boolean> {
  const buyable = (p: Product) => !owned(p) && !soldOut(p);
  return {
    afford: (p) => buyable(p) && price(p) > 0 && price(p) <= coins,
    deal: (p) => buyable(p) && Boolean(p.discount),
    soon: (p) => buyable(p) && p.remaining != null && p.remaining > 0 && p.remaining <= 5,
    boosters: (p) => buyable(p) && p.type === "booster",
    free: (p) => buyable(p) && !p.price_coins,
  };
}

/** A product as a tile: its art (which tells its kind, stock and level), rarity, kind, price or owned. */
function Tile({ product, onOpen }: { product: Product; onOpen: (p: Product) => void }) {
  const t = useT();
  const gear = useEquipment();
  const mine = owned(product);
  const worn = mine && gear.equipped(product);
  const rarity = product.rarity ?? "common";
  return (
    <li
      className="vitrine-tile"
      data-rarity={rarity}
      data-owned={mine || undefined}
      data-soldout={soldOut(product) || undefined}
    >
      <Link
        to={`/marketplace/products/${product.key}`}
        className="vitrine-tile__open"
        onClick={(event) => {
          if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
          event.preventDefault();
          onOpen(product);
        }}
      >
        <span className="vitrine-tile__art">
          <LazyArt product={product} />
        </span>
        {soldOut(product) ? (
          <span className="vitrine-tile__flags">
            <span className="vitrine-flag">{t("marketplace:stock.soldOut")}</span>
          </span>
        ) : null}
        <span className="vitrine-tile__meta">
          <span className="vitrine-tile__kind">
            <span className="vitrine-tile__gem" aria-hidden="true" />
            {t(`marketplace:rarity.${rarity}`)} · {productTypeLabel(t, product.type)}
          </span>
          <strong className="vitrine-tile__name">{product.name}</strong>
          <span className="vitrine-tile__price">
            {mine ? (
              <span className="vitrine-tile__mine">
                <Icon name="check" size={14} />
                {t(worn ? "marketplace:equip.equipped" : "marketplace:product.owned")}
              </span>
            ) : product.price_coins ? (
              <Price product={product} compact />
            ) : (
              <span className="ds-badge">{t("marketplace:purchase.free")}</span>
            )}
          </span>
        </span>
      </Link>
    </li>
  );
}

/** The featured products, one large at a time, turning by themselves (not while pointed at or focused). */
function Spotlight({ items, onOpen }: { items: Product[]; onOpen: (p: Product) => void }) {
  const t = useT();
  const describe = useDescribe();
  const [index, setIndex] = useState(0);
  const [held, setHeld] = useState(false);
  useEffect(() => {
    const still =
      held ||
      items.length < 2 ||
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ||
      document.documentElement.dataset.motion === "none";
    if (still) return;
    const timer = window.setInterval(() => setIndex((i) => (i + 1) % items.length), 8000);
    return () => window.clearInterval(timer);
  }, [held, items.length]);
  const current = items[index % Math.max(1, items.length)];
  if (!current) return null;
  return (
    <section
      className="vitrine-spotlight"
      data-rarity={current.rarity ?? "common"}
      aria-label={t("marketplace:vitrine.spotlight")}
      onMouseEnter={() => setHeld(true)}
      onMouseLeave={() => setHeld(false)}
      onFocus={() => setHeld(true)}
      onBlur={() => setHeld(false)}
    >
      <div key={current.key} className="vitrine-spotlight__slide">
        <span className="vitrine-spotlight__art">
          <LazyArt product={current} size="sheet" />
        </span>
        <div className="vitrine-spotlight__text">
          <span className="vitrine-spotlight__eyebrow">
            <Icon name="star" size={14} />
            {t("marketplace:vitrine.spotlight")} · {t(`marketplace:rarity.${current.rarity ?? "common"}`)}
            <span className="visually-hidden">
              {t("marketplace:vitrine.slide", { index: index + 1, total: items.length })}
            </span>
          </span>
          <h2>{current.name}</h2>
          {describe(current) ? <p>{describe(current)}</p> : null}
          <div className="vitrine-spotlight__actions">
            {owned(current) ? (
              <span className="vitrine-tile__mine">
                <Icon name="check" size={16} /> {t("marketplace:product.owned")}
              </span>
            ) : current.price_coins ? (
              <Price product={current} />
            ) : null}
            <Button variant="primary" onClick={() => onOpen(current)}>
              {t("marketplace:vitrine.see")}
              <Icon name="chevron-right" size={16} />
            </Button>
          </div>
        </div>
      </div>
      {items.length > 1 ? (
        <div className="vitrine-spotlight__thumbs">
          {items.map((p, i) => (
            <button
              key={p.key}
              type="button"
              className="vitrine-spotlight__thumb"
              data-rarity={p.rarity ?? "common"}
              aria-pressed={i === index}
              aria-label={p.name}
              title={p.name}
              onClick={() => setIndex(i)}
            >
              <LazyArt product={p} size="mini" />
            </button>
          ))}
        </div>
      ) : null}
    </section>
  );
}

/** A row of picks that scrolls sideways, with its arrows and « See all ». */
function Rail({
  icon,
  title,
  items,
  onAll,
  children,
}: {
  icon: string;
  title: string;
  items: Product[];
  onAll: () => void;
  children: (p: Product) => ReactNode;
}) {
  const t = useT();
  const list = useRef<HTMLUListElement>(null);
  const slide = (way: number) =>
    list.current?.scrollBy({ left: way * list.current.clientWidth * 0.85, behavior: "smooth" });
  if (!items.length) return null;
  return (
    <section className="vitrine-rail" aria-label={title}>
      <header className="vitrine-rail__head">
        <h2>
          <Icon name={icon} size={18} />
          {title}
          <span className="vitrine-count">{items.length}</span>
        </h2>
        <span className="vitrine-rail__nav">
          <button
            type="button"
            className="vitrine-rail__arrow"
            onClick={() => slide(-1)}
            aria-label={t("marketplace:vitrine.prev")}
          >
            <Icon name="chevron-left" size={16} />
          </button>
          <button
            type="button"
            className="vitrine-rail__arrow"
            onClick={() => slide(1)}
            aria-label={t("marketplace:vitrine.next")}
          >
            <Icon name="chevron-right" size={16} />
          </button>
          <Button variant="ghost" onClick={onAll}>
            {t("marketplace:vitrine.seeAll")}
          </Button>
        </span>
      </header>
      <ul ref={list} className="vitrine-rail__list">
        {items.slice(0, RAIL).map(children)}
      </ul>
    </section>
  );
}

/** A product opened in a side panel: the same sheet and purchase as the classic shop, the browsing kept. */
function ProductPanel({ product, onClose }: { product: Product; onClose: () => void }) {
  const t = useT();
  const full = useProduct(product.key);
  const data = full.data ?? product;
  useEffect(() => {
    window.addEventListener(BOOSTER_EVENT, onClose);
    return () => window.removeEventListener(BOOSTER_EVENT, onClose);
  }, [onClose]);
  return (
    <Drawer
      open
      onOpenChange={(open) => (open ? undefined : onClose())}
      title={data.name}
      closeLabel={t("marketplace:purchase.close")}
      trigger={<span hidden />}
      footer={
        <>
          <TryOn product={data} />
          <div data-protected="">
            <PurchaseBar product={data} />
          </div>
        </>
      }
    >
      <div className="vitrine-sheet">
        <ProductSheet product={data} />
      </div>
    </Drawer>
  );
}

export default function VitrinePage() {
  const t = useT();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const [shown, setShown] = useState(PAGE);
  const [opened, setOpened] = useState<Product | null>(null);
  const progression = useProgression().data;
  const coins = progression?.coins ?? 0;
  const products = useProducts({ category: "", q: q.trim() });
  const pluginShelves = usePluginShelves();
  const departments = useMemo(
    () =>
      withPluginShelves(
        DEPARTMENTS,
        pluginShelves,
        (products.data ?? []).map((p) => p.type),
      ),
    [pluginShelves, products.data],
  );

  const department = departments.find((d) => d.key === params.get("d"));
  const shelf = department?.shelves.find((s) => s.key === params.get("s"));
  const pick = params.get("pick") as Pick | null;
  const sort = (SORTS as readonly string[]).includes(params.get("sort") ?? "")
    ? (params.get("sort") as (typeof SORTS)[number])
    : "recommended";
  const rarity = params.get("r") ?? "";
  const only = (params.get("only") ?? "").split(",").filter(Boolean);
  const home = !department && !pick && !q.trim();

  const set = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [name, value] of Object.entries(changes)) {
      if (value) next.set(name, value);
      else next.delete(name);
    }
    setShown(PAGE);
    setParams(next);
  };
  const go = (d: string | null, s: string | null = null) => set({ d, s, pick: null });
  const toggle = (flag: string) =>
    set({ only: (only.includes(flag) ? only.filter((f) => f !== flag) : [...only, flag]).join(",") || null });

  const all = products.data ?? [];
  const rule = picks(coins);
  const counts = useMemo(() => {
    const byDepartment: Record<string, number> = {};
    const byShelf: Record<string, number> = {};
    for (const p of all) {
      const key = departmentOfProduct(p, departments);
      byDepartment[key] = (byDepartment[key] ?? 0) + 1;
      for (const s of departments.find((d) => d.key === key)?.shelves ?? []) {
        if (onShelf(s, p)) byShelf[`${key}/${s.key}`] = (byShelf[`${key}/${s.key}`] ?? 0) + 1;
      }
    }
    return { byDepartment, byShelf };
  }, [all, departments]);
  const affordable = all.filter(rule.afford).length;

  const listed = useMemo(
    () =>
      all
        .filter((p) => !department || departmentOfProduct(p, departments) === department.key)
        .filter((p) => !shelf || onShelf(shelf, p))
        .filter((p) => !pick || rule[pick]?.(p))
        .filter((p) => !rarity || p.rarity === rarity)
        .filter((p) => !only.includes("afford") || rule.afford(p))
        .filter((p) => !only.includes("unowned") || !owned(p))
        .filter((p) => !only.includes("deal") || Boolean(p.discount))
        .sort(ORDER[sort]),
    [all, department, departments, shelf, pick, rarity, only, sort, rule],
  );

  // a product sheet asked for from elsewhere (« ?product=key »)
  const wanted = params.get("product");
  useEffect(() => {
    if (!wanted || !products.data) return;
    const found = products.data.find((p) => p.key === wanted);
    if (found) setOpened(found);
    const next = new URLSearchParams(params);
    next.delete("product");
    setParams(next, { replace: true });
  }, [wanted, products.data, params, setParams]);

  const tile = (p: Product) => <Tile key={p.key} product={p} onOpen={setOpened} />;
  const spotlight = all
    .filter((p) => p.featured && !soldOut(p))
    .sort(ORDER.rarity)
    .slice(0, 6);
  const heading = shelf
    ? shelfLabel(t, shelf)
    : department
      ? t(`marketplace:department.${department.key}`)
      : pick
        ? t(`marketplace:vitrine.pick.${pick}`)
        : q.trim()
          ? t("marketplace:vitrine.searchResults", { q: q.trim() })
          : t("marketplace:vitrine.everything");

  return (
    <div className="vitrine">
      <PageHeader
        icon="store"
        title={t("marketplace:vitrine.title")}
        context={t("marketplace:vitrine.intro")}
        primary={{
          label: t("marketplace:vitrine.classic"),
          icon: "shop",
          onSelect: () => navigate("/marketplace"),
        }}
      />

      <div className="vitrine__layout">
        <aside className="vitrine-side" aria-label={t("marketplace:vitrine.nav")}>
          <div className="vitrine-wallet">
            <span className="vitrine-wallet__label">
              <Icon name="wallet" size={14} />
              {t("marketplace:vitrine.wallet")}
            </span>
            <CoinBadge amount={coins} label={t("gamification:value.coins")} />
            <button
              type="button"
              className="vitrine-wallet__afford"
              onClick={() => set({ d: null, s: null, pick: "afford" })}
            >
              {t("marketplace:vitrine.affordCount", { count: affordable })}
            </button>
          </div>

          <label className="vitrine-search">
            <Icon name="search" size={16} />
            <span className="visually-hidden">{t("marketplace:catalog.search")}</span>
            <input
              type="search"
              value={q}
              maxLength={64}
              placeholder={t("marketplace:catalog.search")}
              onChange={(e) => {
                setQ(e.target.value);
                setShown(PAGE);
              }}
            />
          </label>

          <nav className="vitrine-nav">
            <button
              type="button"
              className="vitrine-nav__item"
              aria-current={home ? "page" : undefined}
              onClick={() => {
                setQ("");
                setParams({});
              }}
            >
              <Icon name="sparkles" size={16} />
              <span>{t("marketplace:vitrine.home")}</span>
            </button>
            {departments.map((d: Department) => {
              const open = department?.key === d.key;
              return (
                <div key={d.key} className="vitrine-nav__group" data-open={open || undefined}>
                  <button
                    type="button"
                    className="vitrine-nav__item"
                    aria-current={open && !shelf ? "page" : undefined}
                    aria-expanded={open}
                    onClick={() => go(d.key)}
                  >
                    <Icon name={d.icon} size={16} />
                    <span>{t(`marketplace:department.${d.key}`)}</span>
                    <span className="vitrine-count">{counts.byDepartment[d.key] ?? 0}</span>
                  </button>
                  {open && d.shelves.length > 1 ? (
                    <ul className="vitrine-nav__shelves">
                      {d.shelves.map((s) =>
                        counts.byShelf[`${d.key}/${s.key}`] ? (
                          <li key={s.key}>
                            <button
                              type="button"
                              aria-current={shelf?.key === s.key ? "page" : undefined}
                              onClick={() => go(d.key, s.key)}
                            >
                              <span>{shelfLabel(t, s)}</span>
                              <span className="vitrine-count">{counts.byShelf[`${d.key}/${s.key}`]}</span>
                            </button>
                          </li>
                        ) : null,
                      )}
                    </ul>
                  ) : null}
                </div>
              );
            })}
          </nav>

          <footer className="vitrine-side__links">
            <Link to="/marketplace/owned">
              <Icon name="package" size={14} />
              {t("marketplace:vitrine.purchases")}
            </Link>
            <Link to="/marketplace/reserve">
              <Icon name="gift" size={14} />
              {t("marketplace:vitrine.reserve")}
            </Link>
          </footer>
        </aside>

        <main className="vitrine__main">
          {products.isPending ? (
            <Skeleton shape="tile" count={6} label={t("marketplace:vitrine.title")} />
          ) : null}
          {products.isError ? (
            <FunctionalState state="unavailable" onRetry={() => products.refetch()} />
          ) : null}

          {products.data && home ? (
            <>
              <Spotlight items={spotlight} onOpen={setOpened} />
              {(
                [
                  ["afford", "wallet"],
                  ["deal", "flame"],
                  ["soon", "hourglass"],
                  ["boosters", "sparkles"],
                  ["free", "gift"],
                ] as const
              ).map(([key, icon]) => (
                <Rail
                  key={key}
                  icon={icon}
                  title={t(`marketplace:vitrine.pick.${key}`)}
                  items={all.filter(rule[key]).sort(key === "afford" ? ORDER.priceDesc : ORDER.recommended)}
                  onAll={() => set({ pick: key })}
                >
                  {tile}
                </Rail>
              ))}
            </>
          ) : null}

          {products.data && !home ? (
            <section className="vitrine-browse" aria-label={heading}>
              <header className="vitrine-browse__head">
                <h2>
                  {heading}
                  <span className="vitrine-count">
                    {t("marketplace:vitrine.results", { count: listed.length })}
                  </span>
                </h2>
                {department && department.shelves.length > 1 ? (
                  <fieldset className="vitrine-chips" aria-label={t("marketplace:shop.byType")}>
                    <button type="button" aria-pressed={!shelf} onClick={() => go(department.key)}>
                      {t("marketplace:vitrine.all")}
                    </button>
                    {department.shelves.map((s) =>
                      counts.byShelf[`${department.key}/${s.key}`] ? (
                        <button
                          key={s.key}
                          type="button"
                          aria-pressed={shelf?.key === s.key}
                          onClick={() => go(department.key, s.key)}
                        >
                          <Icon name={s.icon} size={14} />
                          {shelfLabel(t, s)}
                        </button>
                      ) : null,
                    )}
                  </fieldset>
                ) : null}
              </header>

              <div className="vitrine-tools">
                <label className="vitrine-sort">
                  <span>{t("marketplace:vitrine.sort")}</span>
                  <select
                    value={sort}
                    onChange={(e) => set({ sort: e.target.value === "recommended" ? null : e.target.value })}
                  >
                    {SORTS.map((s) => (
                      <option key={s} value={s}>
                        {t(`marketplace:vitrine.sortBy.${s}`)}
                      </option>
                    ))}
                  </select>
                </label>
                <fieldset className="vitrine-chips" aria-label={t("marketplace:shop.rarity")}>
                  {RARITIES.map((r) => (
                    <button
                      key={r}
                      type="button"
                      data-rarity={r}
                      aria-pressed={rarity === r}
                      onClick={() => set({ r: rarity === r ? null : r })}
                    >
                      <span className="vitrine-tile__gem" aria-hidden="true" />
                      {t(`marketplace:rarity.${r}`)}
                    </button>
                  ))}
                </fieldset>
                <fieldset className="vitrine-chips" aria-label={t("marketplace:vitrine.filters")}>
                  {ONLY.map((flag) => (
                    <button
                      key={flag}
                      type="button"
                      aria-pressed={only.includes(flag)}
                      onClick={() => toggle(flag)}
                    >
                      {only.includes(flag) ? <Icon name="check" size={14} /> : null}
                      {t(`marketplace:vitrine.only.${flag}`)}
                    </button>
                  ))}
                </fieldset>
              </div>

              {listed.length ? (
                <>
                  <ul className="vitrine-grid">{listed.slice(0, shown).map(tile)}</ul>
                  {listed.length > shown ? (
                    <div className="vitrine-more">
                      <Button variant="secondary" onClick={() => setShown(shown + PAGE)}>
                        {t("marketplace:vitrine.more", { count: listed.length - shown })}
                      </Button>
                    </div>
                  ) : null}
                </>
              ) : (
                <EmptyState
                  icon="shop"
                  title={t("marketplace:shop.nothing")}
                  action={
                    <Button
                      variant="secondary"
                      onClick={() => {
                        setQ("");
                        set({ r: null, only: null, pick: null, sort: null });
                      }}
                    >
                      {t("marketplace:shop.reset")}
                    </Button>
                  }
                />
              )}
            </section>
          ) : null}
        </main>
      </div>
      {opened ? <ProductPanel product={opened} onClose={() => setOpened(null)} /> : null}
    </div>
  );
}
