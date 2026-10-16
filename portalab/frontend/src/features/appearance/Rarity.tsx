import { Icon } from "../../design-system/components/Icon";
import { isPremiumAmbient } from "../../design-system/themes/premium/PremiumAmbient";
import { gpuLook } from "../../design-system/visuals/gpu";
import { externalProduct } from "../../design-system/visuals/registry";
import { useT } from "../../i18n/hooks/useT";

/**
 * #72: the rarity of a look sold in the shop (common, rare, epic, legendary) — a small tag in its colour,
 * shown on the choice; the choice itself carries ``data-rarity`` for an outline of the same colour. Free
 * looks show nothing.
 */
export function RarityTag({ rarity }: { rarity?: string | null | undefined }) {
  const t = useT();
  if (!rarity) return null;
  return (
    <span className="rarity-tag" data-rarity={rarity}>
      <Icon name="gem" size={11} />
      {t(`notifications:universe.rarity.${rarity}`)}
    </span>
  );
}

/** The rarity of ``key`` in a catalog list (``undefined`` when free). */
export function rarityIn(
  list: ReadonlyArray<{ key: string; rarity?: string | null }> | undefined,
  key: string,
): string | undefined {
  return list?.find((c) => c.key === key)?.rarity ?? undefined;
}

/** #71: drawn by the graphics chip (shaders, particles) — high quality, not a CSS animation. */
export function HdTag({ large = false }: { large?: boolean }) {
  const t = useT();
  return (
    <span className="hd-tag" data-large={large || undefined} title={t("notifications:universe.hdHint")}>
      <Icon name="cpu" size={large ? 14 : 11} />
      {t("notifications:universe.hd")}
      <span className="visually-hidden"> — {t("notifications:universe.hdHint")}</span>
    </span>
  );
}

/** Whether this ambience is drawn in high quality (« live weather » switches between premium ones). */
export function isHdAmbient(kind: string | null | undefined): boolean {
  return Boolean(kind) && (kind === "weather" || isPremiumAmbient(kind as string));
}

/** #73, #77: the level badges drawn by the graphics chip (028: their pack says it). */
export function isHdLevelBadge(look: string | null | undefined): boolean {
  return Boolean(gpuLook("level_badge", look));
}

/** 028: a product drawn by the graphics chip — its element's own fragment, or what it names: an ambience
 * drawn in high quality, a live banner, a badge's or title's style. */
function isHdKey(key: string): boolean {
  if (externalProduct(key)?.kind === "glsl") return true;
  if (key.startsWith("ambient_")) return isHdAmbient(key.slice(8));
  if (key.startsWith("banner_live_")) return isHdAmbient(key.slice(12));
  return false;
}

/** #71: whether a shop product is (or, for a pack, holds) an ambience drawn in high quality. */
export function isHdProduct(product: {
  key?: string;
  type: string;
  preview?: Record<string, unknown> | null;
}): boolean {
  if (product.key && isHdKey(product.key)) return true;
  const preview = product.preview ?? {};
  if (product.type === "ambient" || product.type === "profile_background") {
    const kind = preview.ambient ?? preview.background;
    return typeof kind === "string" && isHdAmbient(kind);
  }
  if (product.type === "profile_banner" && typeof preview.banner === "string") {
    return preview.banner.startsWith("live-") && isHdAmbient(preview.banner.slice(5));
  }
  if ((product.type === "badge" || product.type === "title") && typeof preview.style === "string") {
    return Boolean(gpuLook(product.type, preview.style));
  }
  if (product.type === "bundle" && Array.isArray(preview.products)) {
    return (preview.products as unknown[]).some((key) => typeof key === "string" && isHdKey(key));
  }
  return false;
}
