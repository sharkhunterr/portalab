import { Link } from "react-router";
import { useT } from "../../i18n/hooks/useT";
import { registerWidgetComponent, type WidgetProps } from "../dashboard/widgets/registry";
import { FeedText } from "./feed/FeedText";

interface ActivityItem {
  id: string;
  kind?: string;
  actor_id: string;
  actor_name: string | null;
  params: Record<string, unknown>;
}

/** Dashboard widget ``community.activity`` (spec 012 T015): the latest entries the viewer may see. */
function ActivityWidget({ payload }: WidgetProps) {
  const t = useT();
  const items = ((payload.data ?? {}) as { items?: ActivityItem[] }).items ?? [];
  return (
    <div className="ds-stack">
      <ul className="widget-list">
        {items.map((item) => (
          <li key={item.id}>
            <FeedText
              kind={item.kind ?? ""}
              actorId={item.actor_id}
              actorName={item.actor_name}
              params={item.params}
            />
          </li>
        ))}
      </ul>
      <Link to="/community/feed">{t("community:widget.activity.open")}</Link>
    </div>
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
