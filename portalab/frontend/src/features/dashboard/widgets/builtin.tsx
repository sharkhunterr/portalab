import { Link } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { useNavigationView } from "../../../shell/nav/NavigationProvider";
import { useShellStrings } from "../../../shell/strings";
import { registerWidgetComponent, type WidgetProps } from "./registry";

/** First-party widgets (spec 009 T013): welcome / next steps and the services health summary. */
function Welcome({ payload }: WidgetProps) {
  const strings = useShellStrings();
  const { view } = useNavigationView();
  const steps = ((payload.data ?? {}) as { steps?: Array<{ label_key: string; route: string }> }).steps ?? [];
  const iconOf = (route: string) =>
    view.commands.find((c) => c.route === route)?.icon ??
    view.personal.find((e) => e.route === route)?.icon ??
    "chevron-right";
  return (
    <ul className="widget-shortcuts">
      {steps.map((step) => (
        <li key={step.route}>
          <Link to={step.route} className="widget-shortcut">
            <span className="widget-shortcut__icon" aria-hidden="true">
              <Icon name={iconOf(step.route)} size={20} />
            </span>
            {strings.label(step.label_key)}
          </Link>
        </li>
      ))}
    </ul>
  );
}

const STATE_KEYS: Record<string, string> = {
  operational: "operational",
  degraded: "degraded",
  unavailable: "unavailable",
  maintenance: "maintenance",
  unknown: "unknown",
};

function ServicesHealth({ payload }: WidgetProps) {
  const t = useT();
  const data = (payload.data ?? {}) as {
    total?: number;
    counts?: Record<string, number>;
    items?: Array<{ id: string; name: string; state: string; route: string }>;
  };
  return (
    <div className="widget-services">
      <p>{t("dashboard:services.counts", { count: data.total ?? 0 })}</p>
      <ul className="widget-list">
        {(data.items ?? []).map((item) => (
          <li key={item.id} data-state={STATE_KEYS[item.state] ?? "unknown"}>
            <Link to={item.route}>{item.name}</Link> <span className="widget__meta">{item.state}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

registerWidgetComponent("dashboard.welcome", Welcome);
registerWidgetComponent("health.services_summary", ServicesHealth);
