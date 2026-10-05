import { Link } from "react-router";
import { Avatar } from "../../../design-system/components/Avatar";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { type CommunityShelfInfo, useShelf, useShelves } from "../api";
import { FEED_ICONS, FeedText } from "../feed/FeedText";

interface ShelfItem {
  id: string;
  url?: string;
  display_name?: string;
  kind?: string;
  actor_id?: string;
  actor_name?: string | null;
  params?: Record<string, unknown>;
}

const SHELF_ICONS: Record<string, string> = {
  new_members: "users",
  projects: "lightbulb",
  recent_unlocks: "trophy",
  activity_highlights: "sparkles",
};
const SHELF_MORE: Record<string, string> = {
  new_members: "/community/members",
  projects: "/community/proposals",
  recent_unlocks: "/community/achievements",
  activity_highlights: "/community/feed",
};

function Shelf({ info }: { info: CommunityShelfInfo }) {
  const t = useT();
  const shelf = useShelf(info.key);
  const headingId = `community-shelf-${info.key}`;
  const items = ((shelf.data?.items ?? []) as unknown as ShelfItem[]).slice(0, 6);
  const more = SHELF_MORE[info.key];
  return (
    <section aria-labelledby={headingId} className="community-panel" data-shelf={info.key}>
      <header className="community-panel__head">
        <h3 id={headingId}>
          <span className="community-panel__icon" aria-hidden="true">
            <Icon name={SHELF_ICONS[info.key] ?? "sparkles"} size={16} />
          </span>
          {t(info.label_key)}
        </h3>
        {more ? (
          <Link to={more} className="community-panel__more">
            {t("community:discovery.more")}
            <Icon name="chevron-right" size={14} />
          </Link>
        ) : null}
      </header>
      {shelf.isError || shelf.data?.state === "unavailable" ? (
        <FunctionalState state="unavailable" label={t("community:discovery.unavailable")} />
      ) : null}
      {shelf.data?.state === "no-data" ? (
        <p className="community-panel__empty">
          {t("community:discovery.empty")}{" "}
          {info.empty_action ? (
            <Link to={info.empty_action}>{t("community:discovery.emptyAction")}</Link>
          ) : null}
        </p>
      ) : null}
      {info.key === "new_members" ? (
        <ul className="community-faces">
          {items.map((item) => (
            <li key={item.id}>
              <Link to={item.url ?? "/community/members"}>
                <Avatar
                  name={item.display_name ?? ""}
                  userId={item.id}
                  src={`/api/v1/users/${item.id}/avatar`}
                  size="lg"
                  decorative
                />
                <span>{item.display_name}</span>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <ul className="community-shelf">
          {items.map((item) => (
            <li key={item.id}>
              {item.kind && item.actor_id ? (
                <>
                  <span className="community-shelf__icon" aria-hidden="true">
                    <Icon name={FEED_ICONS[item.kind] ?? "activity"} size={14} />
                  </span>
                  <FeedText
                    kind={item.kind}
                    actorId={item.actor_id}
                    actorName={item.actor_name}
                    params={item.params ?? {}}
                  />
                </>
              ) : (
                <>
                  <span className="community-shelf__icon" aria-hidden="true">
                    <Icon name={SHELF_ICONS[info.key] ?? "sparkles"} size={14} />
                  </span>
                  <Link to={item.url ?? "/community/members"}>{item.display_name}</Link>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** ``/community`` (spec 012 T012; 027 redesign): discovery panels bound by the same visibility as their
 * sources — new faces first, then what needs support, the latest achievements and highlights. */
export function DiscoveryHome() {
  const t = useT();
  const shelves = useShelves();
  return (
    <section aria-label={t("community:discovery.title")} className="ds-stack">
      {shelves.isError ? <FunctionalState state="unavailable" onRetry={() => shelves.refetch()} /> : null}
      <div className="community-shelves">
        {(shelves.data ?? []).map((info) => (
          <Shelf key={info.key} info={info} />
        ))}
      </div>
    </section>
  );
}
