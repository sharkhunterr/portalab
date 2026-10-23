import { Link } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { usePacks } from "./api";
import { PackOpening } from "./PackOpening";

/** Issue 234: my sealed card boosters (a film watched, a season finished, one bought) — in my inventory and on
 * my cards' page; a click on one opens it. */
export function CardBoosters({ inventory = false }: { inventory?: boolean }) {
  const t = useT();
  const packs = usePacks().data ?? [];
  if (!packs.length) return null;
  return (
    <section className="cards-packs" aria-labelledby="cards-packs">
      <h2 id="cards-packs">
        <Icon name="gift" size={18} /> {t("gamification:cards.packs", { count: packs.length })}
        {inventory ? <Link to="/cards">{t("gamification:cards.toCollection")}</Link> : null}
      </h2>
      <ul className="cards-boosters">
        {packs.map((pack) => (
          <li key={pack.id}>
            <PackOpening pack={pack} booster />
          </li>
        ))}
      </ul>
    </section>
  );
}
