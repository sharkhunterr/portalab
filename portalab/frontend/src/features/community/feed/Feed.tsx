import { Link } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useFeed } from "../api";
import { FeedText } from "./FeedText";

/** ``/community/feed`` (spec 012 T010): localized entries with source links, as an accessible list. */
export function Feed() {
  const t = useT();
  const format = useFormat();
  const feed = useFeed();
  const items = feed.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <section aria-labelledby="community-feed" className="ds-stack">
      <h2 id="community-feed">{t("community:feed.title")}</h2>
      {feed.isError ? <FunctionalState state="unavailable" onRetry={() => feed.refetch()} /> : null}
      {feed.isSuccess && items.length === 0 ? (
        <p>
          {t("community:feed.empty")} <Link to="/community">{t("community:feed.emptyAction")}</Link>
        </p>
      ) : null}
      <ul className="community-feed">
        {items.map((item) => (
          <li key={item.id}>
            <FeedText
              kind={item.kind}
              actorId={item.actor_id}
              actorName={item.actor_name}
              params={item.params as Record<string, unknown>}
            />{" "}
            <time dateTime={item.occurred_at} className="community-meta">
              {format.dateTime(item.occurred_at)}
            </time>
          </li>
        ))}
      </ul>
      {feed.hasNextPage ? (
        <Button variant="secondary" onClick={() => feed.fetchNextPage()} disabled={feed.isFetchingNextPage}>
          {t("community:feed.more")}
        </Button>
      ) : null}
    </section>
  );
}
