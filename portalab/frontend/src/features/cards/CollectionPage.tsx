import { useState } from "react";
import { Link } from "react-router";
import { AdminEmpty } from "../../design-system/admin/AdminKit";
import { Icon } from "../../design-system/components/Icon";
import { PageHeader } from "../../design-system/components/PageHeader";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { cardImage, useCardSets, useMyCards, usePacks } from "./api";
import { CardCredit } from "./CardCredit";
import { CardSearch, CardSearchResults } from "./CardSearch";
import { PackOpening } from "./PackOpening";
import { PoolView } from "./PoolView";
import "./cards.css";

/** Issue 229: ``/cards`` — my media cards: my packs to open, then the sets (those I started first). */
export default function CollectionPage() {
  const t = useT();
  const format = useFormat();
  const [q, setQ] = useState("");
  const [started, setStarted] = useState(false);
  const [page, setPage] = useState(0);
  const [view, setView] = useState<"sets" | "pool">("sets");
  const [find, setFind] = useState("");
  const mine = useMyCards().data;
  const packs = usePacks().data ?? [];
  const sets = useCardSets(q, started, page);
  const pages = Math.max(1, Math.ceil((sets.data?.total ?? 0) / 48));
  return (
    <div className="ds-stack">
      <PageHeader icon="layers" title={t("gamification:cards.title")} />
      <CardSearch value={find} onChange={setFind} />
      {find.trim() ? (
        <CardSearchResults query={find} />
      ) : (
        <>
          {mine ? (
            <div className="cards-stats">
              <span>
                <strong>{format.number(mine.unique)}</strong> / {format.number(mine.cards)}{" "}
                {t("gamification:cards.stats.cards")}
              </span>
              <span>
                <strong>{format.number(mine.sets_started)}</strong> / {format.number(mine.sets)}{" "}
                {t("gamification:cards.stats.sets")}
              </span>
              <span>
                <strong>{format.number(mine.copies)}</strong> {t("gamification:cards.stats.copies")}
              </span>
            </div>
          ) : null}
          {packs.length ? (
            <section className="cards-packs" aria-labelledby="cards-packs">
              <h2 id="cards-packs">
                <Icon name="gift" size={18} /> {t("gamification:cards.packs", { count: packs.length })}
              </h2>
              <ul>
                {packs.map((pack) => (
                  <li key={pack.id}>
                    <span>
                      {pack.set_name
                        ? t("gamification:cards.pack.from", { name: pack.set_name })
                        : t("gamification:cards.pack.any")}
                    </span>
                    <PackOpening pack={pack} />
                  </li>
                ))}
              </ul>
            </section>
          ) : (
            <p className="admin-muted">{t("gamification:cards.how")}</p>
          )}
          <fieldset className="cards-views">
            <legend className="visually-hidden">{t("gamification:cards.view")}</legend>
            {(["sets", "pool"] as const).map((key) => (
              <button key={key} type="button" aria-pressed={view === key} onClick={() => setView(key)}>
                <Icon name={key === "sets" ? "layers" : "library"} size={16} />
                {t(`gamification:cards.views.${key}`)}
              </button>
            ))}
          </fieldset>
          {view === "pool" ? (
            <PoolView />
          ) : (
            <>
              <div className="cards-filters">
                <input
                  type="search"
                  value={q}
                  placeholder={t("gamification:cards.search")}
                  aria-label={t("gamification:cards.search")}
                  onChange={(event) => {
                    setQ(event.target.value);
                    setPage(0);
                  }}
                />
                <label>
                  <input
                    type="checkbox"
                    checked={started}
                    onChange={(event) => {
                      setStarted(event.target.checked);
                      setPage(0);
                    }}
                  />
                  {t("gamification:cards.started")}
                </label>
              </div>
              {sets.data && !sets.data.items.length ? (
                <AdminEmpty icon="layers" title={t("gamification:cards.noSets")} />
              ) : null}
              <ul className="cards-sets">
                {(sets.data?.items ?? []).map((set) => (
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
                      <span className="cards-sets__name">{set.name}</span>
                      <span className="cards-sets__progress">
                        <span className="requests-meter">
                          <span
                            style={{
                              inlineSize: `${Math.round((set.owned / Math.max(1, set.size)) * 100)}%`,
                            }}
                          />
                        </span>
                        {set.owned}/{set.size}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
              {pages > 1 ? (
                <nav className="cards-pages" aria-label={t("gamification:cards.pages")}>
                  <button type="button" disabled={page === 0} onClick={() => setPage(page - 1)}>
                    <Icon name="chevron-left" size={16} />
                  </button>
                  <span>
                    {page + 1} / {pages}
                  </span>
                  <button type="button" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>
                    <Icon name="chevron-right" size={16} />
                  </button>
                </nav>
              ) : null}
            </>
          )}
        </>
      )}
      <CardCredit />
    </div>
  );
}
