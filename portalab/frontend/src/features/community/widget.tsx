import { Link } from "react-router";
import { Avatar } from "../../design-system/components/Avatar";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { WidgetHeaderAction } from "../dashboard/frame/actions";
import { registerWidgetComponent, type WidgetProps } from "../dashboard/widgets/registry";
import { FEED_ICONS, FeedText } from "./feed/FeedText";
import "./community.css";

interface ActivityItem {
  id: string;
  kind?: string;
  actor_id: string;
  actor_name: string | null;
  params: Record<string, unknown>;
  occurred_at?: string;
}

function Who({ item }: { item: ActivityItem }) {
  return (
    <span className="widget-activity__who">
      <Avatar
        name={item.actor_name ?? ""}
        userId={item.actor_id}
        src={`/api/v1/users/${item.actor_id}/avatar`}
        size="sm"
        decorative
      />
      <span className="widget-activity__icon" aria-hidden="true">
        <Icon name={FEED_ICONS[item.kind ?? ""] ?? "activity"} size={10} />
      </span>
    </span>
  );
}

/**
 * Dashboard widget ``community.activity`` (spec 012 T015; 027 redesign): the latest entries the viewer may
 * see — who (avatar and what kind of thing), what, and when — as rows that fill the block, in two columns
 * on a wide one; on a single row, the latest only. The whole feed is one click away in the header.
 */
function ActivityWidget({ payload, compact }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const items = ((payload.data ?? {}) as { items?: ActivityItem[] }).items ?? [];
  const when = (item: ActivityItem) =>
    item.occurred_at ? format.relative((Date.parse(item.occurred_at) - Date.now()) / 1000) : null;
  const text = (item: ActivityItem) => (
    <FeedText
      kind={item.kind ?? ""}
      actorId={item.actor_id}
      actorName={item.actor_name}
      params={item.params}
    />
  );
  const latest = items[0];
  if (compact && latest)
    return (
      <div className="widget-activity widget-activity--compact" data-kind={latest.kind}>
        <Who item={latest} />
        <span className="widget-activity__text">{text(latest)}</span>
        <time dateTime={latest.occurred_at}>{when(latest)}</time>
      </div>
    );
  return (
    <>
      <WidgetHeaderAction>
        <Link
          to="/community/feed"
          className="widget-activity__all"
          aria-label={t("community:widget.activity.open")}
          title={t("community:widget.activity.open")}
        >
          <Icon name="chevron-right" size={14} />
        </Link>
      </WidgetHeaderAction>
      <ul className="widget-activity">
        {items.map((item) => (
          <li key={item.id} data-kind={item.kind}>
            <Who item={item} />
            <span className="widget-activity__text">{text(item)}</span>
            <time dateTime={item.occurred_at}>{when(item)}</time>
          </li>
        ))}
      </ul>
    </>
  );
}

registerWidgetComponent("community.activity", ActivityWidget);

interface ProjectItem {
  id: string;
  title: string;
  help_wanted: boolean;
  votes: number;
}

/** Dashboard widget ``community.projects`` (spec 012 T024, REQ-018): proposals open for votes or help. */
function ProjectsWidget({ payload }: WidgetProps) {
  const t = useT();
  const items = ((payload.data ?? {}) as { items?: ProjectItem[] }).items ?? [];
  return (
    <ul className="widget-list">
      {items.map((item) => (
        <li key={item.id}>
          <Link to={`/community/proposals/${item.id}`}>{item.title}</Link> ·{" "}
          {t("community:proposals.votes", { count: item.votes })}
          {item.help_wanted ? ` · ${t("community:proposals.helpWanted")}` : ""}
        </li>
      ))}
    </ul>
  );
}

registerWidgetComponent("community.projects", ProjectsWidget);
