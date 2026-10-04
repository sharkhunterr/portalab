import { Link } from "react-router";
import { CoinBadge } from "../../../design-system/components/Badges";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import type { Product } from "../api";

const TYPE_ICONS: Record<string, string> = {
  badge: "star",
  title: "trophy",
  effect: "sparkles",
  theme: "palette",
  plugin: "plug",
  widget: "dashboard",
  quota: "gauge",
  statistic: "chart",
  feature: "zap",
};

/** A product in the catalog (spec 015 T021): name, type and price in text; ownership stated. */
export function ProductCard({ product }: { product: Product }) {
  const t = useT();
  return (
    <li
      className="ds-card product-card"
      data-type={product.type}
      data-owned={product.owned ? "true" : undefined}
    >
      <span className="product-card__art" aria-hidden="true">
        <Icon name={TYPE_ICONS[product.type] ?? "shop"} size={30} />
      </span>
      <h2 className="product-card__name">
        <Link to={`/marketplace/products/${product.key}`}>{product.name}</Link>
      </h2>
      <p className="product-card__meta">
        <span className="ds-badge">{t(`marketplace:type.${product.type}`)}</span>
        {product.owned ? (
          <span className="ds-badge product-card__owned">{t("marketplace:product.owned")}</span>
        ) : null}
      </p>
      <p className="product-card__price">
        {product.price_coins ? (
          <CoinBadge amount={product.price_coins} label={t("gamification:value.coins")} />
        ) : (
          t("marketplace:purchase.free")
        )}
      </p>
    </li>
  );
}
