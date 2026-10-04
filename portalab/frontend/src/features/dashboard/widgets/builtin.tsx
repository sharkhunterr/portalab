import { Link } from "react-router";
import { StatusBadge, type Tone } from "../../../design-system/admin/AdminKit";
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

const HEALTH_TONES: Record<string, Tone> = {
  operational: "ok",
  degraded: "warn",
  unavailable: "bad",
  maintenance: "info",
  unknown: "neutral",
};

/** Services health (027): a summary line, then one row per service with its state as a badge. */
function ServicesHealth({ payload }: WidgetProps) {
  const t = useT();
  const data = (payload.data ?? {}) as {
    total?: number;
    counts?: Record<string, number>;
    items?: Array<{ id: string; name: string; state: string; route: string }>;
  };
  const troubled = (data.items ?? []).filter((item) => item.state !== "operational").length;
  return (
    <div className="widget-services">
      <p className="widget-services__summary" data-troubled={troubled > 0 || undefined}>
        <Icon name={troubled ? "alert" : "check"} size={18} />
        {troubled
          ? t("dashboard:services.troubled", { count: troubled })
          : t("dashboard:services.allGood", { count: data.total ?? 0 })}
      </p>
      <ul className="widget-rows">
        {(data.items ?? []).map((item) => (
          <li key={item.id} className="widget-row">
            <Link to={item.route}>
              <span className="widget-row__thumb" aria-hidden="true">
                <Icon name="server" size={18} />
              </span>
              <span className="widget-row__main">
                <span className="widget-row__title">{item.name}</span>
              </span>
              <StatusBadge tone={HEALTH_TONES[item.state] ?? "neutral"}>
                {t(`dashboard:health.${HEALTH_TONES[item.state] ? item.state : "unknown"}`)}
              </StatusBadge>
              <Icon name="chevron-right" size={16} className="widget-row__chevron" />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

registerWidgetComponent("dashboard.welcome", Welcome);
registerWidgetComponent("health.services_summary", ServicesHealth);
