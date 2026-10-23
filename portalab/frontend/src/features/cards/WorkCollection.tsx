import { useState } from "react";
import { Link } from "react-router";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { useCardSet } from "./api";
import { Binder } from "./SetPage";
import "./cards.css";

const FIRST = 8; // the cards shown before « all of them »

/** Issue 234: a work's collection on its own page — its cards, those I own in colour, the others as their
 * silhouette; nothing when the work has none. */
export function WorkCollection({ objectId }: { objectId: string }) {
  const t = useT();
  const set = useCardSet(objectId, { quiet: true });
  const [all, setAll] = useState(false);
  const data = set.data;
  if (!data?.cards?.length) return null;
  const shown = all ? data.cards : data.cards.slice(0, FIRST);
  return (
    <section className="cards-work" aria-labelledby="cards-work-title">
      <header className="cards-work__head">
        <h2 id="cards-work-title">
          <Icon name="layers" size={18} /> {t("gamification:cards.work.title")}
        </h2>
        <span className="cards-work__progress">
          {t("gamification:cards.setLine", { code: data.code, owned: data.owned, size: data.size })}
        </span>
        <progress max={data.size || 1} value={data.owned} aria-hidden="true" />
        <Link to={`/cards/sets/${data.key}`}>{t("gamification:cards.work.open")}</Link>
      </header>
      <Binder cards={shown} />
      {data.cards.length > FIRST && !all ? (
        <Button variant="secondary" onClick={() => setAll(true)}>
          {t("gamification:cards.work.all", { count: data.cards.length })}
        </Button>
      ) : null}
    </section>
  );
}
