import { Icon } from "../../../design-system/components/Icon";
import type { Product } from "../api";

/**
 * A product's poster (spec 027 US8): a rarity frame and an art panel with an optional animated effect —
 * shine, glitch, spin, neon or blink (``auto`` picks one from the rarity). Effects are decoration only and
 * stop under reduced motion (global rule on ``data-motion="none"``/``prefers-reduced-motion``).
 */
const TYPE_ICONS: Record<string, string> = {
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
};

const AUTO_EFFECT: Record<string, string> = {
  common: "none",
  rare: "shine",
  epic: "spin",
  legendary: "neon",
};

export function effectOf(product: Pick<Product, "poster_effect" | "rarity">): string {
  const effect = product.poster_effect ?? "auto";
  return effect === "auto" ? (AUTO_EFFECT[product.rarity ?? "common"] ?? "none") : effect;
}

export function ProductPoster({ product, size = "md" }: { product: Product; size?: "md" | "lg" }) {
  const icon = product.icon ?? TYPE_ICONS[product.type] ?? "shop";
  return (
    <span
      className="product-poster"
      data-rarity={product.rarity ?? "common"}
      data-effect={effectOf(product)}
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
