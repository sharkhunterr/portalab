import { useEffect, useState } from "react";
import { Link } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { cardImage, useCardPool, useCardSets } from "./api";
import { Binder } from "./SetPage";

/** What is typed, once the typing stops (a search per pause, not per key). */
function useSettled(value: string, ms = 250): string {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value), ms);
    return () => window.clearTimeout(timer);
  }, [value, ms]);
  return settled;
}

/**
 * Issue 229: one search for everything of the cards — the sets (a film, a series), the people (an actor, a
 * director: all their cards) and the cards themselves (by a name, a character, a work) — as one types.
 */
export function CardSearch({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const t = useT();
  return (
    <div className="cards-search">
      <Icon name="search" size={18} />
      <input
        type="search"
        value={value}
        placeholder={t("gamification:cards.find.placeholder")}
        aria-label={t("gamification:cards.find.label")}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}

export function CardSearchResults({ query }: { query: string }) {
  const t = useT();
  const format = useFormat();
  const settled = useSettled(query.trim());
  const sets = useCardSets(settled, false, 0);
  const cards = useCardPool({ q: settled, rarity: "", kind: "", country: "", owned: false, page: 0 });
  const items = cards.data?.items ?? [];
  // the people among the cards found: all their cards in one place
  const people = [
    ...new Map(
      items.filter((c) => c.person && c.kind !== "title").map((c) => [c.person as string, c]),
    ).values(),
  ].slice(0, 12);
  if (!settled) return null;
  const nothing = sets.data && cards.data && !sets.data.items.length && !items.length;
  return (
    <div className="cards-results">
      {nothing ? (
        <p className="admin-muted">{t("gamification:cards.find.nothing", { query: settled })}</p>
      ) : null}
      {sets.data?.items.length ? (
        <section aria-labelledby="found-sets">
          <h2 id="found-sets">
            {t("gamification:cards.find.sets", { count: format.number(sets.data.total) })}
          </h2>
          <ul className="cards-sets">
            {sets.data.items.slice(0, 12).map((set) => (
              <li key={set.key} data-started={set.owned > 0 || undefined}>
                <Link to={`/cards/sets/${set.key}`}>
                  <span className="cards-sets__poster">
                    {set.poster ? (
                      <img src={cardImage(set.poster, "w342") ?? ""} alt="" loading="lazy" />
                    ) : (
                      <Icon name="film" size={28} />
                    )}
                    <span className="cards-sets__code">{set.code}</span>
                  </span>
                  <span className="cards-sets__name">
                    {set.name}
                    {set.year ? ` (${set.year})` : ""}
                  </span>
                  <span className="admin-muted">
                    {set.owned}/{set.size}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {people.length ? (
        <section aria-labelledby="found-people">
          <h2 id="found-people">{t("gamification:cards.find.people")}</h2>
          <ul className="cards-people">
            {people.map((card) => (
              <li key={card.person}>
                <Link to={`/cards/people?ref=${encodeURIComponent(card.person ?? "")}`}>
                  <span className="cards-people__face">
                    {card.art ? <img src={cardImage(card.art, "w185") ?? ""} alt="" loading="lazy" /> : null}
                  </span>
                  {card.name}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {items.length ? (
        <section aria-labelledby="found-cards">
          <h2 id="found-cards">
            {t("gamification:cards.find.cards", { count: format.number(cards.data?.total ?? 0) })}
          </h2>
          <Binder cards={items.slice(0, 24)} />
        </section>
      ) : null}
    </div>
  );
}
