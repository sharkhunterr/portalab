import { Icon } from "../../design-system/components/Icon";
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
