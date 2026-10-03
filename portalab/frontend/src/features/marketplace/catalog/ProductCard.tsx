import { Link } from "react-router";
import { useT } from "../../../i18n/hooks/useT";
import type { Product } from "../api";

/** A product in the catalog (spec 015 T021): name, type and price in text; ownership stated. */
export function ProductCard({ product }: { product: Product }) {
  const t = useT();
  return (
    <li className="ds-card ds-stack">
      <h2>
        <Link to={`/marketplace/products/${product.key}`}>{product.name}</Link>
      </h2>
      <p className="ds-badge">
        {t(`marketplace:type.${product.type}`)} ·{" "}
        {product.price_coins
          ? t("marketplace:purchase.price", { price: product.price_coins })
          : t("marketplace:purchase.free")}
        {product.owned ? ` · ${t("marketplace:product.owned")}` : ""}
      </p>
    </li>
  );
}
