import { Link } from "react-router";
import type { Tone } from "../../../design-system/admin/AdminKit";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useNavigationView } from "../../../shell/nav/NavigationProvider";
import { useShellStrings } from "../../../shell/strings";
import { CONNECTOR_ICON } from "../../services/connectorIcons";
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

interface ServiceItem {
  id: string;
  name: string;
  state: string;
  route: string;
  connector?: string;
  importance?: string;
  availability?: number | null;
}

function servicesData(payload: WidgetProps["payload"]) {
  return (payload.data ?? {}) as { total?: number; counts?: Record<string, number>; items?: ServiceItem[] };
}

/** How many services work, as a ring: the share that works in colour, the rest in its state's colour. */
function HealthRing({ ok, total }: { ok: number; total: number }) {
  const ratio = total ? ok / total : 1;
  return (
    <span
      className="widget-services__ring has-tone"
      data-tone="ok"
      data-all={ok === total || undefined}
      style={{ "--ratio": ratio } as React.CSSProperties}
      aria-hidden="true"
    >
      <span>
        {ok}/{total}
      </span>
    </span>
  );
}

/**
 * Services health (027 redesign): a ring with how many work and a chip per state in trouble, then a tile
 * per service — its kind's icon ringed with its state, its name, its state in words and its last 24 hours
 * as a thin bar. Trouble first, then the most important. Narrow blocks list them.
 */
function ServicesHealth({ payload }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const data = servicesData(payload);
  const items = data.items ?? [];
  const counts = data.counts ?? {};
  const total = data.total ?? items.length;
  const ok = counts.operational ?? 0;
  const troubled = total - ok;
  return (
    <div className="widget-services">
      <div
        className="widget-services__head has-tone"
        data-tone={troubled ? "warn" : "ok"}
        data-troubled={troubled > 0 || undefined}
      >
        <HealthRing ok={ok} total={total} />
        <p className="widget-services__summary">
          <strong>
            {troubled
              ? t("dashboard:services.troubled", { count: troubled })
              : t("dashboard:services.allGood", { count: total })}
          </strong>
          <span className="widget-services__chips">
            {Object.entries(counts)
              .filter(([state, count]) => state !== "operational" && count > 0)
              .map(([state, count]) => (
                <span
                  key={state}
                  className="widget-services__chip has-tone"
                  data-tone={HEALTH_TONES[state] ?? "neutral"}
                >
                  {count} {t(`dashboard:health.${HEALTH_TONES[state] ? state : "unknown"}`)}
                </span>
              ))}
          </span>
        </p>
        <Link to="/services" className="widget-services__all">
          {t("dashboard:services.all")}
          <Icon name="chevron-right" size={14} />
        </Link>
      </div>
      <ul className="widget-services__grid">
        {items.map((item) => {
          const tone = HEALTH_TONES[item.state] ?? "neutral";
          const availability = typeof item.availability === "number" ? item.availability : null;
          return (
            <li key={item.id}>
              <Link to={item.route} className="widget-service has-tone" data-tone={tone}>
                <span className="widget-service__icon" aria-hidden="true">
                  <Icon name={CONNECTOR_ICON[item.connector ?? ""] ?? "server"} size={18} />
                </span>
                <span className="widget-service__text">
                  <span className="widget-service__name">
                    {item.name}
                    {item.importance === "critical" ? (
                      <Icon name="star" size={11} className="widget-service__critical" />
                    ) : null}
                  </span>
                  <span className="widget-service__state">
                    <span className="status-dot" data-tone={tone} />
                    {t(`dashboard:health.${HEALTH_TONES[item.state] ? item.state : "unknown"}`)}
                  </span>
                </span>
                {availability !== null ? (
                  <span
                    className="widget-service__uptime"
                    title={t("dashboard:services.uptime", { value: format.percent(availability) })}
                  >
                    <span className="widget-service__bar" aria-hidden="true">
                      <span style={{ inlineSize: `${Math.round(availability * 100)}%` }} />
                    </span>
                    <span>{format.percent(availability)}</span>
                  </span>
                ) : null}
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Services, compact (027): one line — how many work, then a dot per service (its name on hover). */
function ServicesCompact({ payload }: WidgetProps) {
  const t = useT();
  const data = servicesData(payload);
  const items = data.items ?? [];
  const total = data.total ?? items.length;
  const ok = data.counts?.operational ?? 0;
  const troubled = total - ok;
  return (
    <Link
      to="/services"
      className="widget-services-compact has-tone"
      data-tone={troubled ? "warn" : "ok"}
      data-troubled={troubled > 0 || undefined}
    >
      <span className="widget-services-compact__status">
        <Icon name={troubled ? "alert" : "check"} size={16} />
        <strong>
          {ok}/{total}
        </strong>
        <span className="widget-services-compact__label">
          {troubled
            ? t("dashboard:services.troubled", { count: troubled })
            : t("dashboard:services.allGood", { count: total })}
        </span>
      </span>
      <ul className="widget-services-compact__dots">
        {items.map((item) => {
          const tone = HEALTH_TONES[item.state] ?? "neutral";
          const label = `${item.name} — ${t(`dashboard:health.${HEALTH_TONES[item.state] ? item.state : "unknown"}`)}`;
          return (
            <li key={item.id} className="has-tone" data-tone={tone} title={label}>
              <Icon name={CONNECTOR_ICON[item.connector ?? ""] ?? "server"} size={14} />
              <span className="visually-hidden">{label}</span>
            </li>
          );
        })}
      </ul>
    </Link>
  );
}

/** Service links (027): the configured services as tiles — open the service, see its state at a glance. */
function ServiceLinks({ payload }: WidgetProps) {
  const t = useT();
  const items =
    (
      (payload.data ?? {}) as {
        items?: Array<{
          id: string;
          name: string;
          connector: string;
          state: string;
          link: string | null;
          route: string;
        }>;
      }
    ).items ?? [];
  return (
    <ul className="widget-links">
      {items.map((item) => {
        const body = (
          <>
            <span className="widget-links__icon" aria-hidden="true">
              <Icon name={CONNECTOR_ICON[item.connector] ?? "server"} size={22} />
              <span
                className="widget-links__dot status-dot"
                data-tone={HEALTH_TONES[item.state] ?? "neutral"}
              />
            </span>
            <span className="widget-links__name">{item.name}</span>
            <span className="widget-links__state">
              {t(`dashboard:health.${HEALTH_TONES[item.state] ? item.state : "unknown"}`)}
            </span>
          </>
        );
        return (
          <li key={item.id}>
            {item.link ? (
              <a
                href={item.link}
                target="_blank"
                rel="noopener noreferrer"
                title={t("dashboard:widget.links.open", { name: item.name })}
              >
                {body}
                <Icon name="link" size={12} className="widget-links__external" />
              </a>
            ) : (
              <Link to={item.route}>{body}</Link>
            )}
          </li>
        );
      })}
    </ul>
  );
}

registerWidgetComponent("dashboard.welcome", Welcome);
registerWidgetComponent("health.service_links", ServiceLinks);
registerWidgetComponent("health.services_summary", ServicesHealth);
registerWidgetComponent("health.services_compact", ServicesCompact);
