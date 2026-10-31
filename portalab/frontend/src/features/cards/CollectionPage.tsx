import { useState } from "react";
import { Link, useSearchParams } from "react-router";
import { AdminEmpty } from "../../design-system/admin/AdminKit";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { PageHeader } from "../../design-system/components/PageHeader";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { type CardsSummary, cardImage, useCardSets, useMyCards, usePacks } from "./api";
import { CardBoosters } from "./CardBoosters";
import { CardCredit } from "./CardCredit";
import { CardSearch, CardSearchResults } from "./CardSearch";
import { PoolView } from "./PoolView";
import "./cards.css";

const VIEWS = ["collection", "boosters", "pool"] as const;
type View = (typeof VIEWS)[number];
const VIEW_ICONS: Record<View, string> = { collection: "layers", boosters: "gift", pool: "library" };

/** #298: where my collection stands — the cards I have of all there are, the sets started, the copies. */
function Summary({ mine }: { mine: CardsSummary }) {
  const t = useT();
  const format = useFormat();
  const share = mine.cards ? Math.round((mine.unique / mine.cards) * 100) : 0;
  return (
    <section className="cards-summary" aria-label={t("gamification:cards.summary")}>
      <div className="cards-summary__main">
        <span>
          <strong>{format.number(mine.unique)}</strong> / {format.number(mine.cards)}{" "}
          {t("gamification:cards.stats.cards")}
        </span>
        <span className="requests-meter" aria-hidden="true">
          <span style={{ inlineSize: `${share}%` }} />
        </span>
        <span className="cards-summary__share">{format.number(share)} %</span>
      </div>
      <div className="cards-stats">
        <span>
          <strong>{format.number(mine.sets_started)}</strong> / {format.number(mine.sets)}{" "}
          {t("gamification:cards.stats.sets")}
        </span>
        <span>
          <strong>{format.number(mine.copies)}</strong> {t("gamification:cards.stats.copies")}
        </span>
      </div>
    </section>
  );
}

/** My sets (those I started, else all of them), as posters with how far each one is. */
function Sets() {
  const t = useT();
  const mine = useMyCards().data;
  const [only, setOnly] = useState<boolean | null>(null);
  const [page, setPage] = useState(0);
  const started = only ?? Boolean(mine?.sets_started);
  const sets = useCardSets("", started, page);
  const pages = Math.max(1, Math.ceil((sets.data?.total ?? 0) / 48));
  return (
    <>
      <fieldset className="cards-views cards-views--small">
        <legend className="visually-hidden">{t("gamification:cards.view")}</legend>
        {([true, false] as const).map((value) => (
          <button
            key={String(value)}
            type="button"
            aria-pressed={started === value}
            onClick={() => {
              setOnly(value);
              setPage(0);
            }}
          >
            {t(value ? "gamification:cards.mySets" : "gamification:cards.allSets")}
          </button>
        ))}
      </fieldset>
      {sets.data && !sets.data.items.length ? (
        <AdminEmpty
          icon="layers"
          title={t(started ? "gamification:cards.noMySets" : "gamification:cards.noSets")}
        />
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
  );
}

/**
 * Issue 229: ``/cards`` — my media cards. #298: the collection first (where it stands, my sets, one search
 * for sets, people and cards), the boosters to open a view of their own (recalled at the top while some
 * wait), and every card there is to look for the ones I miss. The view is in the address (``?vue=``).
 */
export default function CollectionPage() {
  const t = useT();
  const [params, setParams] = useSearchParams();
  const asked = params.get("vue");
  const view: View = (VIEWS as readonly string[]).includes(asked ?? "") ? (asked as View) : "collection";
  const show = (next: View) => setParams(next === "collection" ? {} : { vue: next }, { replace: true });
  const [find, setFind] = useState("");
  const mine = useMyCards().data;
  const packs = usePacks().data ?? [];
  return (
    <div className="ds-stack">
      <PageHeader icon="layers" title={t("gamification:cards.title")} />
      {mine ? <Summary mine={mine} /> : null}
      {packs.length && view !== "boosters" ? (
        <div className="cards-callout">
          <Icon name="gift" size={20} />
          <span>{t("gamification:cards.packs", { count: packs.length })}</span>
          <Button onClick={() => show("boosters")}>{t("gamification:cards.openThem")}</Button>
        </div>
      ) : null}
      <fieldset className="cards-views">
        <legend className="visually-hidden">{t("gamification:cards.view")}</legend>
        {VIEWS.map((key) => (
          <button key={key} type="button" aria-pressed={view === key} onClick={() => show(key)}>
            <Icon name={VIEW_ICONS[key]} size={16} />
            {t(`gamification:cards.views.${key}`)}
            {key === "boosters" && packs.length ? (
              <span className="cards-views__count">{packs.length}</span>
            ) : null}
          </button>
        ))}
      </fieldset>
      {view === "collection" ? (
        <>
          <CardSearch value={find} onChange={setFind} />
          {find.trim() ? <CardSearchResults query={find} /> : <Sets />}
        </>
      ) : null}
      {view === "boosters" ? (
        packs.length ? (
          <CardBoosters />
        ) : (
          <AdminEmpty
            icon="gift"
            title={t("gamification:cards.noPacks")}
            message={t("gamification:cards.how")}
          />
        )
      ) : null}
      {view === "pool" ? <PoolView /> : null}
      <CardCredit />
    </div>
  );
}
