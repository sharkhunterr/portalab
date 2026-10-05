import { Icon } from "../../../design-system/components/Icon";
import type { Product } from "../api";

/**
 * A product's poster (spec 027 US8): a rarity frame and an icon — kept for the admin's lists; the shop draws
 * a pre-rendering instead (``ProductArt``). Animated poster effects were removed (to be rethought).
 */
export const TYPE_ICONS: Record<string, string> = {
  badge: "star",
  title: "trophy",
  effect: "sparkles",
  theme: "palette",
  plugin: "plug",
  widget: "dashboard",
  quota: "inbox",
  statistic: "chart",
  feature: "zap",
  access: "key",
  bundle: "shop",
  ambient: "snowflake",
  profile_background: "sparkles",
  name_style: "feather",
};

export function ProductPoster({ product, size = "md" }: { product: Product; size?: "md" | "lg" }) {
  const icon = product.icon ?? TYPE_ICONS[product.type] ?? "shop";
  return (
    <span
      className="product-poster"
      data-rarity={product.rarity ?? "common"}
      data-size={size}
      aria-hidden="true"
    >
      <span className="product-poster__glow" />
      <span className="product-poster__art">
        <Icon name={icon} size={size === "lg" ? 72 : 44} />
      </span>
    </span>
  );
}
