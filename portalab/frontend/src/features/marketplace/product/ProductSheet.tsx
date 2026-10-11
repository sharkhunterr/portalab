import { useEffect, useState } from "react";
import { Link } from "react-router";
import { usePreferences } from "../../../design-system/a11y/PreferencesProvider";
import type { UiPreferences } from "../../../design-system/a11y/preferences";
import { CoinBadge } from "../../../design-system/components/Badges";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { useNotify } from "../../../design-system/components/Notification";
import { useCelebrate } from "../../../design-system/feedback/Celebration";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { HdTag, isHdProduct } from "../../appearance/Rarity";
import { useHasPermission } from "../../authz/useMyPermissions";
import { showLevelUp } from "../../gamification/levelup/LevelUpMoment";
import { type Product, useAcquire, useDescribe, useProducts } from "../api";
import { Price, priceOf } from "../catalog/Price";
import { ProductArt, TYPE_BADGE_ICON } from "../catalog/ProductArt";
import { useEquipment } from "../equip";
import { ConditionsChecklist } from "./ConditionsChecklist";

/**
 * A product sheet (027), shared by the shop's modal and the product page: a pre-rendering of what it is,
 * its rarity, type and description, what a pack contains (a small card per product, each linking to its
 * own page) or the packs a product is part of (with a link to each), and the facts on the side — price, copies left, minimum level, purchase limit, refund policy and the named conditions.
 */
function PackItem({ item }: { item: Product }) {
  const t = useT();
  const description = useDescribe()(item);
  return (
    <li className="pack-item" data-rarity={item.rarity ?? "common"}>
      <ProductArt product={item} size="mini" />
      <div className="pack-item__text">
        <Link to={`/marketplace/products/${item.key}`} className="pack-item__name">
          {item.name}
        </Link>
        <span className="pack-item__meta">
          <span className="product-card__rarity">{t(`marketplace:rarity.${item.rarity ?? "common"}`)}</span>
          {isHdProduct(item) ? (
            <>
              {" "}
              <HdTag />
            </>
          ) : null}
          {" · "}
          {t(`marketplace:type.${item.type}`)}
        </span>
        {description ? <span className="pack-item__description">{description}</span> : null}
      </div>
      {item.owned ? (
        <span className="product-card__owned">
          <Icon name="check" size={14} /> {t("marketplace:product.owned")}
        </span>
      ) : item.price_coins ? (
        <span className="pack-item__worth">
          <CoinBadge amount={item.price_coins} label={t("gamification:value.coins")} />
        </span>
      ) : null}
    </li>
  );
}

function PackContents({ product }: { product: Product }) {
  const t = useT();
  const products = useProducts({ category: "", q: "" });
  const keys = Array.isArray(product.preview?.products) ? (product.preview.products as string[]) : [];
  const items = keys
    .map((key) => (products.data ?? []).find((p) => p.key === key))
    .filter((p): p is Product => Boolean(p));
  if (!items.length) return null;
  const worth = items.reduce((sum, item) => sum + (item.price_coins ?? 0), 0);
  return (
    <section className="product-sheet__section" aria-labelledby="pack-contents">
      <h3 id="pack-contents">
        {t("marketplace:sheet.packContents", { count: items.length })}
        {worth && product.price_coins && worth > product.price_coins ? (
          <span className="product-sheet__saving">
            {t("marketplace:sheet.saving", { coins: worth - product.price_coins })}
          </span>
        ) : null}
      </h3>
      <ul className="pack-items">
        {items.map((item) => (
          <PackItem key={item.key} item={item} />
        ))}
      </ul>
    </section>
  );
}

/**
 * 027: the packs a product is part of — the product is one item among each, the pack sells them together
 * for less; each links to the pack's page.
 */
function InPacks({ product }: { product: Product }) {
  const t = useT();
  const products = useProducts({ category: "", q: "" });
  const packs = (products.data ?? []).filter(
    (p) =>
      p.type === "bundle" &&
      Array.isArray(p.preview?.products) &&
      (p.preview.products as string[]).includes(product.key),
  );
  if (!packs.length) return null;
  return (
    <section className="product-sheet__section" aria-labelledby="in-packs">
      <h3 id="in-packs">{t("marketplace:sheet.inPacks", { count: packs.length })}</h3>
      <ul className="pack-refs">
        {packs.map((pack) => (
          <li key={pack.key} className="pack-ref" data-rarity={pack.rarity ?? "common"}>
            <Link to={`/marketplace/products/${pack.key}`} className="pack-ref__name">
              {pack.name}
            </Link>
            <span className="product-card__rarity">{t(`marketplace:rarity.${pack.rarity ?? "common"}`)}</span>
            {pack.owned ? (
              <span className="product-card__owned">
                <Icon name="check" size={14} /> {t("marketplace:product.owned")}
              </span>
            ) : pack.price_coins ? (
              <CoinBadge amount={pack.price_coins} label={t("gamification:value.coins")} />
            ) : null}
            <Link
              to={`/marketplace/products/${pack.key}`}
              className="ds-button ds-button--secondary pack-ref__see"
            >
              {t("marketplace:sheet.seePack")}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Fact({ icon, label, children }: { icon: string; label: string; children: React.ReactNode }) {
  return (
    <div className="product-fact">
      <dt>
        <Icon name={icon} size={16} />
        {label}
      </dt>
      <dd>{children}</dd>
    </div>
  );
}

export function ProductSheet({ product }: { product: Product }) {
  const t = useT();
  const rarity = product.rarity ?? "common";
  const description = useDescribe()(product);
  const policy = product.refund_policy as { refundable?: boolean; window_days?: number; percent?: number };
  const supply = product.supply ?? null;
  const remaining = product.remaining ?? null;
  const checks = (product.eligibility ?? []).filter((c) => c.name !== "stock");
  return (
    <div className="product-sheet" data-rarity={rarity}>
      <ProductArt product={product} size="sheet" />
      <div className="product-sheet__chips">
        <span className="product-chip" data-rarity={rarity}>
          <Icon name="star" size={14} />
          {t(`marketplace:rarity.${rarity}`)}
        </span>
        <span className="product-chip">
          <Icon name={TYPE_BADGE_ICON[product.type] ?? "shop"} size={14} />
          {t(`marketplace:type.${product.type}`)}
        </span>
        {isHdProduct(product) ? <HdTag large /> : null}
        {product.owned ? (
          <span className="product-chip" data-tone="ok">
            <Icon name="check" size={14} />
            {t("marketplace:product.owned")}
          </span>
        ) : null}
      </div>
      <div className="product-sheet__grid">
        <div className="product-sheet__main">
          {description ? <p className="product-sheet__description">{description}</p> : null}
          <section className="product-sheet__section" aria-labelledby="product-what">
            <h3 id="product-what">{t("marketplace:sheet.what")}</h3>
            <p>{t(`marketplace:what.${product.type}`)}</p>
          </section>
          {product.type === "bundle" ? <PackContents product={product} /> : <InPacks product={product} />}
        </div>
        <dl className="product-sheet__facts">
          <Fact icon="coins" label={t("marketplace:sheet.price")}>
            {product.price_coins ? <Price product={product} /> : t("marketplace:purchase.free")}
          </Fact>
          <Fact icon="star" label={t("marketplace:sheet.copies")}>
            {supply === null || remaining === null ? (
              t("marketplace:stock.unlimited")
            ) : (
              <span className="product-stock">
                <span>
                  {remaining === 0
                    ? t("marketplace:stock.soldOut")
                    : t("marketplace:stock.of", { remaining, supply })}
                </span>
                <span className="product-stock__bar" aria-hidden="true">
                  <span style={{ inlineSize: `${Math.round((remaining / supply) * 100)}%` }} />
                </span>
              </span>
            )}
          </Fact>
          {product.min_level ? (
            <Fact icon="trophy" label={t("marketplace:sheet.minLevel")}>
              {t("marketplace:sheet.level", { level: product.min_level })}
            </Fact>
          ) : null}
          {product.min_contribution ? (
            <Fact icon="handshake" label={t("marketplace:sheet.minContribution")}>
              {t("marketplace:sheet.contribution", { points: product.min_contribution })}
            </Fact>
          ) : null}
          {product.limit_count && product.limit_days ? (
            <Fact icon="clock" label={t("marketplace:sheet.limit")}>
              {t("marketplace:sheet.limitValue", { count: product.limit_count, days: product.limit_days })}
            </Fact>
          ) : null}
          <Fact icon="sync" label={t("marketplace:sheet.refund")}>
            {policy.refundable
              ? t("marketplace:sheet.refundValue", {
                  days: policy.window_days ?? 0,
                  percent: policy.percent ?? 100,
                })
              : t("marketplace:sheet.noRefund")}
          </Fact>
          {checks.length ? (
            <div className="product-fact product-fact--wide">
              <dt>
                <Icon name="check" size={16} />
                {t("marketplace:conditions.title")}
              </dt>
              <dd>
                <ConditionsChecklist checks={checks} />
              </dd>
            </div>
          ) : null}
        </dl>
      </div>
    </div>
  );
}

/** What « Try it » puts on for a moment, by product type (never saved). */
function trialOf(product: Product): Partial<UiPreferences> | null {
  const preview = (product.preview ?? {}) as Record<string, unknown>;
  const value = (field: string) => (typeof preview[field] === "string" ? (preview[field] as string) : null);
  switch (product.type) {
    case "theme":
      return value("theme") ? { theme: value("theme") } : null;
    case "palette":
      return value("palette") ? ({ palette: value("palette") } as Partial<UiPreferences>) : null;
    case "ambient":
      return value("ambient") ? ({ ambient: value("ambient") } as Partial<UiPreferences>) : null;
    case "effect":
      return value("effect") ? ({ celebration: value("effect") } as Partial<UiPreferences>) : null;
    case "notification_style":
      return value("style") ? ({ notificationStyle: value("style") } as Partial<UiPreferences>) : null;
    case "level_up":
      return value("animation") ? ({ levelUp: value("animation") } as Partial<UiPreferences>) : null;
    case "notification_animation":
      return value("animation")
        ? ({ notificationAnimation: value("animation") } as Partial<UiPreferences>)
        : null;
    default:
      return null;
  }
}

/**
 * « Try it » (027): the theme, palette, ambient animation, celebration or notification look is put on for
 * as long as the product is open — on the whole portal, behind the sheet — and taken off on close.
 */
export function TryOn({ product }: { product: Product }) {
  const t = useT();
  const { preview, setPreview } = usePreferences();
  const notify = useNotify();
  const celebrate = useCelebrate();
  const trial = trialOf(product);
  const on = Boolean(preview && trial && Object.keys(trial).every((k) => k in preview));
  useEffect(() => () => setPreview(null), [setPreview]); // taken off when the sheet closes
  if (!trial) return null;
  const show = () => {
    if (product.type === "effect") celebrate({ kind: "reward", text: "+40 XP" });
    if (product.type === "level_up") {
      const animation = (product.preview as Record<string, unknown> | undefined)?.animation;
      showLevelUp({ level: 12, preview: typeof animation === "string" ? animation : "classic" });
    }
    if (product.type.startsWith("notification_")) {
      notify({
        severity: "success",
        tone: "reward",
        title: t("notifications:looks.sampleTitle"),
        body: t("notifications:looks.sampleBody"),
        badge: t("notifications:badge.reward"),
      });
    }
  };
  return (
    <Button
      variant="secondary"
      aria-pressed={on}
      onClick={() => {
        if (on) {
          setPreview(null);
          return;
        }
        setPreview(trial);
        setTimeout(show, 120);
      }}
    >
      <Icon name={on ? "close" : "eye"} size={16} />
      {on ? t("marketplace:buy.stopTrying") : t("marketplace:buy.try")}
    </Button>
  );
}

/** Buying from the sheet: « Buy » → a one-line confirmation (price, refund policy) → done or why not. */
export function PurchaseBar({ product }: { product: Product }) {
  const t = useT();
  const canBuy = useHasPermission("marketplace.purchase");
  const acquire = useAcquire(product.key);
  const gear = useEquipment();
  const [confirming, setConfirming] = useState(false);
  const [requestKey, setRequestKey] = useState(() => crypto.randomUUID());
  const policy = product.refund_policy as { refundable?: boolean; window_days?: number; percent?: number };
  const error = acquire.error instanceof ApiError ? acquire.error.code : null;
  if (!canBuy || product.state !== "available") return null;
  if (acquire.isSuccess) {
    return (
      <p role="status" className="purchase-bar__done">
        <Icon name="check" size={16} />
        {t(`marketplace:purchase.done.${acquire.data?.state ?? "active"}`)}
        {acquire.data?.state === "needs_configuration" ? (
          <Link to="/marketplace/owned">{t("marketplace:owned.configure")}</Link>
        ) : null}
      </p>
    );
  }
  const soldOut = product.remaining === 0;
  const unmet = (product.eligibility ?? []).some((c) => !c.met);
  const owned = product.owned && !product.repeatable;
  const blocked = owned ? "owned" : soldOut ? "soldOut" : unmet ? "locked" : null;
  if (owned && gear.wearable(product)) {
    // 027: an owned look — worn now, or one tap to wear it
    return gear.equipped(product) ? (
      <span className="purchase-bar__blocked" data-equipped="">
        <Icon name="check" size={16} />
        {t("marketplace:equip.equippedLong")}
      </span>
    ) : (
      <Button onClick={() => void gear.equip(product)} disabled={gear.pending}>
        <Icon name="sparkles" size={16} />
        {t("marketplace:equip.action")}
      </Button>
    );
  }
  if (blocked) {
    return (
      <span className="purchase-bar__blocked">
        <Icon name={blocked === "owned" ? "check" : "lock"} size={16} />
        {t(`marketplace:buy.${blocked}`)}
      </span>
    );
  }
  if (!confirming) {
    return (
      <Button onClick={() => setConfirming(true)}>
        <Icon name="shop" size={16} />
        {product.price_coins
          ? t("marketplace:buy.cta", { price: priceOf(product) ?? 0 })
          : t("marketplace:buy.free")}
      </Button>
    );
  }
  return (
    <>
      <span className="purchase-bar__text">
        {error ? (
          <span role="alert">{t(`marketplace:purchase.error.${error.split(".")[1] ?? "generic"}`)}</span>
        ) : (
          <>
            {product.price_coins
              ? t("marketplace:buy.confirmText", { price: priceOf(product) ?? 0 })
              : t("marketplace:purchase.free")}{" "}
            <span className="admin-muted">
              {policy.refundable
                ? t("marketplace:purchase.refundable", {
                    days: policy.window_days ?? 0,
                    percent: policy.percent ?? 100,
                  })
                : t("marketplace:purchase.notRefundable")}
            </span>
          </>
        )}
      </span>
      <Button
        variant="ghost"
        onClick={() => {
          setConfirming(false);
          setRequestKey(crypto.randomUUID());
          acquire.reset();
        }}
      >
        {t("marketplace:buy.cancel")}
      </Button>
      <Button onClick={() => acquire.mutate(requestKey)} disabled={acquire.isPending || Boolean(error)}>
        <Icon name="coins" size={16} />
        {t("marketplace:buy.confirm")}
      </Button>
    </>
  );
}
