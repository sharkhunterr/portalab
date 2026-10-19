import { Link } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { CurrencyShort } from "../../design-system/site/SiteLook";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
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
  if (compact && first)
    // 027 (#36): the shop window's first product, its price, and the way to the shop
    return (
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
    );
  return (
    <div className="shop-window">
      <ul className="shop-window__list">
        {items.map((item) => (
          <li key={item.key}>
            <Link
              className="shop-window__item"
              data-rarity={item.rarity ?? "common"}
              to={`/marketplace?product=${encodeURIComponent(item.key)}`}
            >
              <span className="shop-window__art" aria-hidden="true">
                <Icon name={item.icon ?? TYPE_ICONS[item.type] ?? "shop"} size={26} />
                {item.featured ? (
                  <span className="shop-window__star">
                    <Icon name="star" size={11} />
                  </span>
                ) : null}
              </span>
              <span className="shop-window__name">{item.name}</span>
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
            </Link>
          </li>
        ))}
      </ul>
      <Link className="shop-window__all" to="/marketplace">
        <Icon name="shop" size={16} />
        {t("marketplace:widget.featured.all", { count: data.total ?? items.length })}
        <Icon name="chevron-right" size={14} />
      </Link>
    </div>
  );
}

registerWidgetComponent("marketplace.featured", FeaturedWidget);
