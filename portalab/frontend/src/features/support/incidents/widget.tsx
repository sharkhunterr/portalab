import { Link } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { registerWidgetComponent, type WidgetProps } from "../../dashboard/widgets/registry";
import { SeverityBadge, StateSteps, useLasting } from "./IncidentParts";
import "../support.css";

interface Item {
  id: string;
  title: string;
  reference: string;
  route: string;
  state: string;
  severity: string;
  since: string;
  resolved_at: string | null;
  services: number;
}

/** Dashboard widget ``support.open_incidents`` (027 redesign): what is going wrong now — severity, step
 * reached, how long — and what was fixed this week. */
function IncidentsWidget({ payload }: WidgetProps) {
  const t = useT();
  const lasting = useLasting();
  const data = (payload.data ?? {}) as { items?: Item[]; open?: number };
  const items = data.items ?? [];
  return (
    <div className="incidents-widget">
      <p className="incidents-widget__status" data-ok={!data.open || undefined}>
        <Icon name={data.open ? "alert" : "check"} size={16} />
        {data.open ? t("support:incident.count", { count: data.open }) : t("support:incident.allGood")}
      </p>
      <ul className="incidents-widget__list">
        {items.map((item) => (
          <li key={item.id} data-severity={item.severity} data-resolved={item.resolved_at ? true : undefined}>
            <Link to={item.route} className="incidents-widget__item">
              <span className="incidents-widget__top">
                <SeverityBadge severity={item.severity} />
                <span className="incidents-widget__when">
                  {item.resolved_at
                    ? t("support:incident.lasted", { duration: lasting(item.since, item.resolved_at) })
                    : t("support:incident.since", { duration: lasting(item.since) })}
                </span>
              </span>
              <strong>{item.title}</strong>
              <span className="incidents-widget__bottom">
                <StateSteps state={item.state} compact />
                <span>{t(`support:state.${item.state}`)}</span>
                {item.services ? (
                  <span className="incidents-widget__services">
                    <Icon name="server" size={11} />
                    {item.services}
                  </span>
                ) : null}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

registerWidgetComponent("support.incidents", IncidentsWidget);
