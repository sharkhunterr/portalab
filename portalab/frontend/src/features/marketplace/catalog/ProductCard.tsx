import { Link } from "react-router";
import { CoinBadge } from "../../../design-system/components/Badges";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import type { Product } from "../api";
import { ProductPoster } from "./ProductPoster";

/**
 * A product in the shop (spec 015 T021, 027 US8): a collectible card — rarity frame, animated poster,
 * name, type, rarity and price in text (never color alone), ownership stated.
 */
export function ProductCard({
  product,
  as = "li",
  onOpen,
}: {
  product: Product;
  as?: "li" | "div";
  /** 027: open the product in a modal (the link still leads to its page in a new tab or without JS). */
  onOpen?: ((product: Product) => void) | undefined;
}) {
  const t = useT();
  const Tag = as;
  const rarity = product.rarity ?? "common";
  return (
    <Tag
      className="product-card"
      data-type={product.type}
      data-rarity={rarity}
      data-owned={product.owned ? "true" : undefined}
    >
      <ProductPoster product={product} />
      <div className="product-card__body">
        <span className="product-card__rarity">{t(`marketplace:rarity.${rarity}`)}</span>
        <h3 className="product-card__name">
          <Link
            to={`/marketplace/products/${product.key}`}
            onClick={(event) => {
              if (!onOpen || event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
              event.preventDefault();
              onOpen(product);
            }}
          >
            {product.name}
          </Link>
        </h3>
        <span className="product-card__type">{t(`marketplace:type.${product.type}`)}</span>
        <div className="product-card__footer">
          {product.owned ? (
            <span className="product-card__owned">
              <Icon name="check" size={16} /> {t("marketplace:product.owned")}
            </span>
          ) : product.price_coins ? (
            <CoinBadge amount={product.price_coins} label={t("gamification:value.coins")} />
          ) : (
            <span className="ds-badge">{t("marketplace:purchase.free")}</span>
          )}
        </div>
      </div>
    </Tag>
  );
}
