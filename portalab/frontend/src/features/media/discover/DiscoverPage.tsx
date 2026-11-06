import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { AskDialog } from "../../requests/AskDialog";
import { useAskOptions } from "../../requests/api";
import { QuotaSummary } from "../requests/QuotaSummary";
import { useDiscoverSearch } from "./api";
import { DatabaseTitleCard, useDatabaseTitles } from "./DatabaseTitles";
import { DiscoverShelves, RequestableCard } from "./DiscoverShelves";
import "../media.css";
import "./discover.css";

/**
 * #4: « Ask for a title » — a search over what the request service knows (films and series, the library's
 * or not), my quota, then the shelves like Seerr's (trending, popular, upcoming); each title opens its
 * page where one asks for it. Issue 375: books, audiobooks and games too — found in the book and game
 * databases, each opening its sheet — and, for anything else, asking the team.
 */
export function DiscoverPage() {
  const t = useT();
  const [params, setParams] = useSearchParams();
  const [typed, setTyped] = useState(params.get("q") ?? "");
  const [query, setQuery] = useState(typed);
  useEffect(() => {
    const wait = window.setTimeout(() => {
      setQuery(typed.trim());
      setParams(typed.trim() ? { q: typed.trim() } : {}, { replace: true });
    }, 350);
    return () => window.clearTimeout(wait);
  }, [typed, setParams]);
  const found = useDiscoverSearch(query);
  const others = useDatabaseTitles(query);
  const asks = useAskOptions();
  const films = found.data?.items ?? [];
  const books = others.data ?? [];
  return (
    <div className="discover-page">
      <PageHeader title={t("media:discover.title")} context={t("media:discover.pitch")} />
      <label className="discover-page__search ds-field">
        <span className="visually-hidden">{t("media:discover.searchLabel")}</span>
        <span className="discover-page__field">
          <Icon name="search" size={18} />
          <input
            type="search"
            value={typed}
            placeholder={t("media:discover.searchPlaceholder")}
            onChange={(event) => setTyped(event.target.value)}
          />
        </span>
      </label>
      <QuotaSummary />
      {query.length > 1 ? (
        <>
          <section className="media-row" aria-label={t("media:discover.results")}>
            {found.isPending || others.isPending ? <FunctionalState state="loading" /> : null}
            {found.isError ? <FunctionalState state="unavailable" onRetry={() => found.refetch()} /> : null}
            {found.data && others.data && !films.length && !books.length ? (
              <p className="media-muted">{t("media:discover.nothing", { query })}</p>
            ) : null}
            {films.length ? (
              <ul className="media-grid" aria-label={t("media:discover.results")}>
                {films.map((item) => (
                  <RequestableCard key={`${item.kind}-${item.tmdb_id}`} item={item} />
                ))}
              </ul>
            ) : null}
          </section>
          {books.length ? (
            <section className="media-row" aria-label={t("media:discover.otherTitles")}>
              <h3>{t("media:discover.otherTitles")}</h3>
              <ul className="media-grid" aria-label={t("media:discover.otherTitles")}>
                {books.map((item) => (
                  <DatabaseTitleCard key={item.route} item={item} />
                ))}
              </ul>
            </section>
          ) : null}
          {asks.data?.kinds.length ? (
            <p className="media-muted">
              {t("media:discover.askTeam")}{" "}
              <AskDialog
                start={{ title: query }}
                trigger={
                  <button type="button" className="media-person__ask">
                    <Icon name="plus" size={14} />
                    {t("media:ask.page.title")}
                  </button>
                }
              />
            </p>
          ) : null}
        </>
      ) : (
        <DiscoverShelves />
      )}
    </div>
  );
}

export default DiscoverPage;
