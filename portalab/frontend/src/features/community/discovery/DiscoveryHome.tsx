import { Link } from "react-router";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { type CommunityShelfInfo, useShelf, useShelves } from "../api";
import { FeedText } from "../feed/FeedText";

interface ShelfItem {
  id: string;
  url?: string;
  display_name?: string;
  kind?: string;
  actor_id?: string;
  actor_name?: string | null;
  params?: Record<string, unknown>;
}

function Shelf({ info }: { info: CommunityShelfInfo }) {
  const t = useT();
  const shelf = useShelf(info.key);
  const headingId = `community-shelf-${info.key}`;
  const items = (shelf.data?.items ?? []) as unknown as ShelfItem[];
  return (
    <section aria-labelledby={headingId} className="ds-card ds-stack">
      <h3 id={headingId}>{t(info.label_key)}</h3>
      {shelf.isError || shelf.data?.state === "unavailable" ? (
        <FunctionalState state="unavailable" label={t("community:discovery.unavailable")} />
      ) : null}
      {shelf.data?.state === "no-data" ? (
        <p>
          {t("community:discovery.empty")}{" "}
          {info.empty_action ? (
            <Link to={info.empty_action}>{t("community:discovery.emptyAction")}</Link>
          ) : null}
        </p>
      ) : null}
      <ul className="community-shelf">
        {items.map((item) => (
          <li key={item.id}>
            {item.kind && item.actor_id ? (
              <FeedText
                kind={item.kind}
                actorId={item.actor_id}
                actorName={item.actor_name}
                params={item.params ?? {}}
              />
            ) : (
              <Link to={item.url ?? "/community/members"}>{item.display_name}</Link>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** ``/community`` (spec 012 T012): discovery shelves bound by the same visibility as their sources. */
export function DiscoveryHome() {
  const t = useT();
  const shelves = useShelves();
  return (
    <section aria-labelledby="community-discover" className="ds-stack">
      <h2 id="community-discover">{t("community:discovery.title")}</h2>
      {shelves.isError ? <FunctionalState state="unavailable" onRetry={() => shelves.refetch()} /> : null}
      <div className="community-shelves">
        {(shelves.data ?? []).map((info) => (
          <Shelf key={info.key} info={info} />
        ))}
      </div>
    </section>
  );
}
