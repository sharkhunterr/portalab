import { CoinBadge } from "../../../design-system/components/Badges";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import type { Product } from "../api";

/** What a product costs now (027): the campaign price beside the struck catalog price, and the campaign. */
export function Price({ product, compact = false }: { product: Product; compact?: boolean }) {
  const t = useT();
  const coins = t("gamification:value.coins");
  if (!product.price_coins) return null;
  const deal = product.discount && product.price_now !== null && product.price_now !== undefined;
  if (!deal || !product.discount) return <CoinBadge amount={product.price_coins} label={coins} />;
  return (
    <span className="price-deal" data-compact={compact || undefined}>
      <s className="price-deal__was">
        <span className="visually-hidden">{t("marketplace:deal.was", { price: product.price_coins })}</span>
        <span aria-hidden="true">{product.price_coins}</span>
      </s>
      <CoinBadge amount={product.price_now ?? product.price_coins} label={coins} />
      <span className="price-deal__badge" title={product.discount.name}>
        <Icon name="flame" size={12} />
        {compact
          ? t("marketplace:deal.percent", { percent: product.discount.percent })
          : t("marketplace:deal.campaign", {
              percent: product.discount.percent,
              name: product.discount.name,
            })}
      </span>
    </span>
  );
}

/** The price a purchase charges: the campaign price when one applies. */
export const priceOf = (product: Product): number | null | undefined =>
  product.price_now ?? product.price_coins;
