import { useId, useState } from "react";
import { Link } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { type GroupOut, type ItemOut, kindKey, runSearch, type SearchParams } from "../api";

/**
 * One result group (spec 008 T017): its own functional state (an unavailable source never hides the
 * others), highlighted snippets rendered as text (``<mark>`` from structured segments — never HTML from
 * the server) and "more results" paging within the group.
 */
export function Snippet({ item }: { item: ItemOut }) {
  if (!item.snippet.length) return null;
  return (
    <p className="search-result__snippet">
      {item.snippet.map((segment, index) =>
        // biome-ignore lint/suspicious/noArrayIndexKey: segments are positional and never reordered
        segment.hit ? <mark key={index}>{segment.text}</mark> : <span key={index}>{segment.text}</span>,
      )}
    </p>
  );
}

export function ResultGroup({ group, params }: { group: GroupOut; params: SearchParams }) {
  const t = useT();
  const headingId = useId();
  const [extra, setExtra] = useState<ItemOut[]>([]);
  const [cursor, setCursor] = useState<string | null>(group.next_cursor);
  const [loading, setLoading] = useState(false);
  const items = [...group.items, ...extra];
  async function more() {
    setLoading(true);
    try {
      const page = await runSearch({ ...params, kinds: [group.kind] }, cursor);
      const next = page.groups.find((g) => g.kind === group.kind);
      setExtra((current) => [...current, ...(next?.items ?? [])]);
      setCursor(next?.next_cursor ?? null);
    } finally {
      setLoading(false);
    }
  }
  return (
    <section aria-labelledby={headingId} className="search-group" data-kind={group.kind}>
      <h3 id={headingId}>
        {t(kindKey(group.label_key))} <span className="search-group__count">({items.length})</span>
      </h3>
      {group.state === "unavailable" ? (
        <FunctionalState state="unavailable" label={t("search:groupUnavailable")} />
      ) : (
        <ul className="search-group__items">
          {items.map((item) => (
            <li key={`${item.kind}:${item.id}`} className="search-result">
              <Link to={item.url_ref} className="search-result__title">
                {item.title}
              </Link>
              {item.matched_by === "semantic" ? (
                <span className="search-result__badge">{t("search:mode.semantic")}</span>
              ) : null}
              <Snippet item={item} />
            </li>
          ))}
        </ul>
      )}
      {cursor && group.state !== "unavailable" ? (
        <Button variant="secondary" onClick={more} disabled={loading} aria-busy={loading || undefined}>
          {t("search:more")}
        </Button>
      ) : null}
    </section>
  );
}
