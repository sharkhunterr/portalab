import { type FormEvent, useEffect, useId, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useAnnounce } from "../../design-system/a11y/Announce";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { PageHeader } from "../../design-system/components/PageHeader";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useT } from "../../i18n/hooks/useT";
import { type Mode, type SearchParams, useSearch } from "./api";
import { AssistPanel } from "./assist/AssistPanel";
import { FilterBar } from "./filters/FilterBar";
import { ResultGroup } from "./groups/ResultGroup";
import { HistoryList } from "./history/HistoryList";

/**
 * Global search page (spec 008 T017; US1/US3): grouped, filtered results immediately — never waiting for
 * the assistant, which is asked separately. The URL holds the query, type and facet filters
 * (``?q=…&type=services&f.state=error``) so filtering updates in place and views are shareable.
 */
const MODES: Mode[] = ["mixed", "exact", "semantic"];

export function paramsFrom(search: URLSearchParams): SearchParams {
  const filters: Record<string, string[]> = {};
  for (const [key, value] of search.entries()) {
    if (key.startsWith("f.")) filters[key.slice(2)] = [...(filters[key.slice(2)] ?? []), value];
  }
  const mode = search.get("mode");
  return {
    q: search.get("q") ?? "",
    mode: MODES.includes(mode as Mode) ? (mode as Mode) : "mixed",
    kinds: search.getAll("type"),
    filters,
  };
}

export function toSearch(params: SearchParams): URLSearchParams {
  const out = new URLSearchParams();
  if (params.q) out.set("q", params.q);
  if (params.mode !== "mixed") out.set("mode", params.mode);
  for (const kind of params.kinds) out.append("type", kind);
  for (const [key, values] of Object.entries(params.filters))
    for (const v of values) out.append(`f.${key}`, v);
  return out;
}

export function SearchPage() {
  const t = useT();
  const headingId = useId();
  const announce = useAnnounce();
  const [urlParams, setUrlParams] = useSearchParams();
  const params = paramsFrom(urlParams);
  const [draft, setDraft] = useState(params.q);
  useEffect(() => setDraft(params.q), [params.q]);
  const search = useSearch(params);
  const update = (next: SearchParams) => setUrlParams(toSearch(next), { replace: next.q === params.q });
  const total = search.data?.total;
  useEffect(() => {
    if (total !== undefined) announce(t("search:results", { count: total }));
  }, [total, announce, t]);

  function submit(event: FormEvent) {
    event.preventDefault();
    update({ ...params, q: draft.trim() });
  }

  const groups = search.data?.groups ?? [];
  const items = groups.flatMap((group) => group.items);
  const started = Boolean(params.q || params.kinds.length || Object.keys(params.filters).length);
  return (
    <section aria-labelledby={headingId} className="search-page">
      <PageHeader titleId={headingId} level={2} icon="search" title={t("search:title")} />
      <search className="search-hero">
        {/* #67: one large field, the matching as a button group */}
        <form onSubmit={submit} className="search-form">
          <label className="search-form__field">
            <span className="visually-hidden">{t("search:label")}</span>
            <Icon name="search" size={20} />
            <input
              type="search"
              name="q"
              value={draft}
              placeholder={t("search:placeholder")}
              onChange={(event) => setDraft(event.target.value)}
              maxLength={256}
            />
          </label>
          <Button type="submit">{t("search:submit")}</Button>
        </form>
        <fieldset className="ds-subnav search-modes">
          <legend className="visually-hidden">{t("search:mode")}</legend>
          {MODES.map((mode) => (
            <button
              key={mode}
              type="button"
              aria-pressed={params.mode === mode}
              onClick={() => update({ ...params, mode })}
            >
              {t(`search:mode.${mode}`)}
            </button>
          ))}
        </fieldset>
      </search>
      {!started ? (
        <>
          <p>{t("search:start")}</p>
          <HistoryList onPick={(q) => update({ ...params, q })} />
        </>
      ) : null}
      {search.isError ? <FunctionalState state="error" onRetry={() => search.refetch()} /> : null}
      {search.isPending && started ? <FunctionalState state="loading" /> : null}
      {search.data ? (
        <div className="search-layout">
          <aside className="search-side">
            <FilterBar groups={groups} params={params} onChange={update} />
            <AssistPanel key={params.q} query={params.q} items={items} />
          </aside>
          <div className="search-results" aria-busy={search.isFetching || undefined}>
            <p role="status" className="search-total">
              <strong>{t("search:results", { count: search.data.total })}</strong>
              {search.data.semantic === "unavailable" && params.mode !== "exact" ? (
                <span className="search-notice">{t("search:semanticUnavailable")}</span>
              ) : null}
            </p>
            {search.data.total === 0 ? (
              <section className="ds-panel">
                <p>{t("search:empty", { query: params.q })}</p>
                <p>{t("search:emptyHint")}</p>
                <Link className="ds-button ds-button--secondary" to="/services">
                  {t("search:browse")}
                </Link>
              </section>
            ) : null}
            {groups
              .filter((group) => group.items.length > 0 || group.state !== "ok")
              .map((group) => (
                <ResultGroup key={`${group.kind}:${search.data.request_id}`} group={group} params={params} />
              ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

export default SearchPage;
