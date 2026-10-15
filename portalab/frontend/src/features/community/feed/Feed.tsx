import { Link } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { EmptyState } from "../../../design-system/components/Placeholders";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useFeed } from "../api";
import { MemberAvatar } from "../MemberFace";
import { FEED_ICONS, FeedText } from "./FeedText";

/** ``/community/feed`` (spec 012 T010; 027 redesign): a timeline grouped by day — who, what (an icon per
 * kind) and when — as an accessible list. */
export function Feed() {
  const t = useT();
  const format = useFormat();
  const feed = useFeed();
  const items = feed.data?.pages.flatMap((page) => page.items) ?? [];
  const days: Array<{ day: string; items: typeof items }> = [];
  for (const item of items) {
    const day = item.occurred_at.slice(0, 10);
    const last = days.at(-1);
    if (last && last.day === day) last.items.push(item);
    else days.push({ day, items: [item] });
  }
  return (
    <section aria-label={t("community:feed.title")} className="ds-stack">
      {feed.isError ? <FunctionalState state="unavailable" onRetry={() => feed.refetch()} /> : null}
      {feed.isSuccess && items.length === 0 ? (
        <EmptyState
          icon="activity"
          title={t("community:feed.empty")}
          action={
            <Link className="ds-button ds-button--secondary" to="/community">
              {t("community:feed.emptyAction")}
            </Link>
          }
        />
      ) : null}
      {days.map((group) => (
        <section
          key={group.day}
          className="community-day"
          aria-label={format.date(group.items[0]?.occurred_at ?? group.day, "long")}
        >
          <h3 className="community-day__title">
            {format.date(group.items[0]?.occurred_at ?? group.day, "long")}
          </h3>
          <ol className="community-timeline">
            {group.items.map((item) => (
              <li key={item.id} className="community-timeline__item" data-kind={item.kind}>
                <span className="community-timeline__who">
                  <MemberAvatar
                    id={item.actor_id}
                    name={item.actor_name ?? ""}
                    look={item.look}
                    anonymous={item.anonymous}
                  />
                  <span className="community-timeline__icon" aria-hidden="true">
                    <Icon name={FEED_ICONS[item.kind] ?? "activity"} size={11} />
                  </span>
                </span>
                <span className="community-timeline__text">
                  <FeedText
                    kind={item.kind}
                    actorId={item.actor_id}
                    actorName={item.actor_name}
                    anonymous={item.anonymous}
                    params={item.params as Record<string, unknown>}
                    look={item.look}
                  />
                </span>
                <time dateTime={item.occurred_at} className="community-meta">
                  {format.time(item.occurred_at)}
                </time>
              </li>
            ))}
          </ol>
        </section>
      ))}
      {feed.hasNextPage ? (
        <Button variant="secondary" onClick={() => feed.fetchNextPage()} disabled={feed.isFetchingNextPage}>
          {t("community:feed.more")}
        </Button>
      ) : null}
    </section>
  );
}
