import { type FormEvent, useEffect, useId, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useAnnounce } from "../../design-system/a11y/Announce";
import { Button } from "../../design-system/components/Button";
import { SelectField, TextField } from "../../design-system/components/Field";
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
      <h2 id={headingId}>{t("search:title")}</h2>
      <search>
        <form onSubmit={submit} className="ds-stack ds-stack--row search-form">
          <TextField
            label={t("search:label")}
            type="search"
            name="q"
            value={draft}
            placeholder={t("search:placeholder")}
            onChange={(event) => setDraft(event.target.value)}
            maxLength={256}
          />
          <SelectField
            label={t("search:mode")}
            value={params.mode}
            onChange={(event) => update({ ...params, mode: event.target.value as Mode })}
          >
            {MODES.map((mode) => (
              <option key={mode} value={mode}>
                {t(`search:mode.${mode}`)}
              </option>
            ))}
          </SelectField>
          <Button type="submit">{t("search:submit")}</Button>
        </form>
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
          <div className="search-results" aria-busy={search.isFetching || undefined}>
            <p role="status">{t("search:results", { count: search.data.total })}</p>
            {search.data.semantic === "unavailable" && params.mode !== "exact" ? (
              <p className="search-notice">{t("search:semanticUnavailable")}</p>
            ) : null}
            <FilterBar groups={groups} params={params} onChange={update} />
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
          <AssistPanel key={params.q} query={params.q} items={items} />
        </div>
      ) : null}
    </section>
  );
}

export default SearchPage;
