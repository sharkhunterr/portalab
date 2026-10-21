import { useEffect, useState } from "react";
import { Link } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { CurrencyShort } from "../../design-system/site/SiteLook";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { WidgetHeaderLink } from "../dashboard/frame/actions";
import { CompactLine } from "../dashboard/widgets/compact";
import { registerWidgetComponent, type WidgetProps } from "../dashboard/widgets/registry";
import { TYPE_ICONS } from "./catalog/ProductPoster";
import "./marketplace.css";
import { productTypeLabel } from "./typeLabel";

interface Featured {
  key: string;
  name: string;
  type: string;
  rarity?: string | null;
  icon?: string | null;
  featured?: boolean;
  price: number | null;
}

/** Dashboard widget ``marketplace.featured`` (spec 015 T033; 027 redesign): the shop window — what is
 * featured, then what is new, each opening its product sheet in the shop. */
function FeaturedWidget({ payload, compact }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const data = (payload.data ?? {}) as { items?: Featured[]; total?: number };
  const items = data.items ?? [];
  const first = items[0];
  const open = <WidgetHeaderLink to="/marketplace" label={t("marketplace:widget.featured.open")} />;
  if (compact && first)
    // 027 (#36): the shop window's first product, its price, and the way to the shop
    return (
      <>
        {open}
        <CompactLine
          to={`/marketplace?product=${encodeURIComponent(first.key)}`}
          icon={first.icon ?? TYPE_ICONS[first.type] ?? "shop"}
          title={first.name}
          detail={productTypeLabel(t, first.type)}
          end={
            first.price ? (
              <>
                <Icon name="coins" size={12} />
                {format.number(first.price)}
                <CurrencyShort />
              </>
            ) : (
              t("marketplace:purchase.free")
            )
          }
        />
      </>
    );
  return (
    <>
      {open}
      <ShopCarousel items={items} />
    </>
  );
}

const EVERY_MS = 5000;

/**
 * Issue 185: the shop window as a carousel — one product at a time, filling the block (its art grows with
 * the height), dots to pick one, turning by itself every few seconds (paused while pointed at or focused,
 * never with reduced motion).
 */
function ShopCarousel({ items }: { items: Featured[] }) {
  const t = useT();
  const format = useFormat();
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const count = items.length;
  useEffect(() => {
    if (paused || count < 2) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const timer = window.setInterval(() => setIndex((i) => (i + 1) % count), EVERY_MS);
    return () => window.clearInterval(timer);
  }, [paused, count]);
  if (!count) return null;
  const shown = Math.min(index, count - 1);
  return (
    <section
      className="shop-carousel"
      aria-roledescription="carousel"
      aria-label={t("marketplace:widget.featured.carousel")}
      onPointerEnter={() => setPaused(true)}
      onPointerLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <div className="shop-carousel__track" style={{ transform: `translateX(-${shown * 100}%)` }}>
        {items.map((item, at) => (
          <Link
            key={item.key}
            className="shop-carousel__slide"
            data-rarity={item.rarity ?? "common"}
            to={`/marketplace?product=${encodeURIComponent(item.key)}`}
            aria-hidden={at !== shown || undefined}
            tabIndex={at === shown ? 0 : -1}
          >
            <span className="shop-carousel__art" aria-hidden="true">
              <Icon name={item.icon ?? TYPE_ICONS[item.type] ?? "shop"} size={36} />
              {item.featured ? (
                <span className="shop-window__star">
                  <Icon name="star" size={11} />
                </span>
              ) : null}
            </span>
            <span className="shop-carousel__text">
              <span className="shop-carousel__name">{item.name}</span>
              <span className="shop-window__meta">
                <span className="shop-window__type">{productTypeLabel(t, item.type)}</span>
                <span className="shop-window__price">
                  {item.price ? (
                    <>
                      <Icon name="coins" size={12} />
                      {format.number(item.price)}
                      <CurrencyShort />
                    </>
                  ) : (
                    t("marketplace:purchase.free")
                  )}
                </span>
              </span>
            </span>
          </Link>
        ))}
      </div>
      {count > 1 ? (
        <div className="shop-carousel__dots">
          {items.map((item, at) => (
            <button
              key={item.key}
              type="button"
              className="shop-carousel__dot"
              aria-current={at === shown || undefined}
              aria-label={t("marketplace:widget.featured.slide", { n: at + 1, total: count })}
              onClick={() => setIndex(at)}
            />
          ))}
        </div>
      ) : null}
    </section>
  );
}

registerWidgetComponent("marketplace.featured", FeaturedWidget);
