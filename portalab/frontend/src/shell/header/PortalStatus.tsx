import * as PopoverPrimitive from "@radix-ui/react-popover";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../../api/client";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { useNavigationView } from "../nav/NavigationProvider";
import { DAY, isRunning, upcoming, useMaintenances, useOpenIncidents } from "../status/portalStatus";
import { useNow } from "../status/StatusBanner";

const WEEK = 7 * DAY;
const ICONS = {
  ok: "heart",
  incident: "alert",
  maintenance: "wrench",
  degraded: "warning",
  planned: "wrench",
} as const;
type State = keyof typeof ICONS;

/**
 * 027: the portal's state at a glance, shared by incidents and maintenances — a heart beating while all is
 * well, a warning when services are in trouble, a wrench during (or the day before) a maintenance, the
 * danger sign during an incident, with how many. Pressed, a small window under it tells the details: the
 * open incidents (severity, step, since when), the maintenances of the week (running or when), the
 * services in trouble, and the way to the status and incidents pages.
 */
export function IncidentsButton() {
  const t = useT();
  const format = useFormat();
  const now = useNow();
  const { view } = useNavigationView();
  const canRead = view.groups.some((g) => g.entries.some((e) => e.key === "health.services"));
  const open = useOpenIncidents();
  const windows = useMaintenances();
  const services = useQuery({
    queryKey: ["shell", "health-summary"],
    enabled: canRead,
    retry: false,
    refetchInterval: 60_000,
    queryFn: async () =>
      (
        (await api.GET("/api/v1/services/health")).data as unknown as {
          items: Array<{ state: string; degrades_portal?: boolean }>;
        }
      ).items,
  });
  const incidents = Array.isArray(open.data) ? open.data : [];
  const week = upcoming(windows.data, WEEK, now);
  const running = week.filter((m) => isRunning(m, now));
  const soon = week.filter((m) => !isRunning(m, now) && Date.parse(m.starts_at) - now < DAY);
  const items = Array.isArray(services.data) ? services.data : [];
  // services whose alerting rule leaves them out of the portal's health (internal ones) do not count
  const troubled = items.filter(
    (s) => s.degrades_portal !== false && (s.state === "unavailable" || s.state === "degraded"),
  ).length;
  if (!incidents.length && !week.length && !items.length) return null;
  const state: State = incidents.length
    ? "incident"
    : running.length
      ? "maintenance"
      : troubled
        ? "degraded"
        : soon.length
          ? "planned"
          : "ok";
  const count = {
    incident: incidents.length,
    maintenance: running.length,
    degraded: troubled,
    planned: soon.length,
    ok: 0,
  }[state];
  const label =
    state === "incident"
      ? t("shell:incidents", { count })
      : state === "maintenance"
        ? t("shell:status.maintenanceRunning", { count })
        : state === "degraded"
          ? t("shell:health.degraded", { count })
          : state === "planned"
            ? t("shell:status.maintenancePlanned", { count })
            : t("shell:health.ok");
  return (
    <PopoverPrimitive.Root>
      <PopoverPrimitive.Trigger asChild>
        <button
          type="button"
          className="ds-button ds-button--ghost ds-button--icon shell-health"
          data-state={state}
          aria-label={label}
          title={label}
        >
          <Icon name={ICONS[state]} />
          {count ? (
            <span className="shell-health__count" aria-hidden="true">
              {count > 99 ? "99+" : count}
            </span>
          ) : null}
        </button>
      </PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          className="ds-popover shell-status"
          data-state-tone={state}
          aria-label={t("shell:status.title")}
          sideOffset={6}
          align="end"
          collisionPadding={12}
        >
          <p className="shell-status__head">
            <span className="shell-status__badge" aria-hidden="true">
              <Icon name={ICONS[state]} size={18} />
            </span>
            <span>
              <small>{t("shell:status.title")}</small>
              <strong>{label}</strong>
            </span>
          </p>

          {incidents.length ? (
            <section className="shell-status__group">
              <h3>{t("shell:status.incidents")}</h3>
              <ul>
                {incidents.map((incident) => (
                  <li key={incident.id}>
                    <PopoverPrimitive.Close asChild>
                      <Link
                        to={`/incidents/${incident.id}`}
                        className="shell-status__item"
                        data-severity={incident.severity}
                      >
                        <span className="shell-status__dot" aria-hidden="true" />
                        <span className="shell-status__text">
                          <strong>{incident.title}</strong>
                          <small>
                            {[
                              t(`support:severity.${incident.severity}`),
                              t(`support:state.${incident.state}`),
                              format.relative((Date.parse(incident.created_at) - now) / 1000),
                            ].join(" · ")}
                          </small>
                        </span>
                        <Icon name="chevron-right" size={14} />
                      </Link>
                    </PopoverPrimitive.Close>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {week.length ? (
            <section className="shell-status__group">
              <h3>{t("shell:status.maintenance")}</h3>
              <ul>
                {week.map((m) => {
                  const on = isRunning(m, now);
                  return (
                    <li key={m.id}>
                      <PopoverPrimitive.Close asChild>
                        <Link
                          to="/incidents"
                          className="shell-status__item"
                          data-maintenance={on ? "running" : "planned"}
                        >
                          <span className="shell-status__dot" aria-hidden="true" />
                          <span className="shell-status__text">
                            <strong>{m.title}</strong>
                            <small>
                              {on
                                ? `${t("support:maintenance.running")} · ${t("support:banner.endsIn", {
                                    when: format.relative((Date.parse(m.ends_at) - now) / 1000),
                                  })}`
                                : `${format.dateTime(m.starts_at)} → ${format.time(m.ends_at)}`}
                            </small>
                          </span>
                          <Icon name="chevron-right" size={14} />
                        </Link>
                      </PopoverPrimitive.Close>
                    </li>
                  );
                })}
              </ul>
            </section>
          ) : null}

          {canRead && items.length ? (
            <section className="shell-status__group">
              <h3>{t("shell:status.services")}</h3>
              <PopoverPrimitive.Close asChild>
                <Link
                  to="/services"
                  className="shell-status__item"
                  data-services={troubled ? "trouble" : "ok"}
                >
                  <span className="shell-status__dot" aria-hidden="true" />
                  <span className="shell-status__text">
                    <strong>
                      {troubled ? t("shell:health.degraded", { count: troubled }) : t("shell:health.ok")}
                    </strong>
                  </span>
                  <Icon name="chevron-right" size={14} />
                </Link>
              </PopoverPrimitive.Close>
            </section>
          ) : null}

          <footer className="shell-status__foot">
            {canRead ? (
              <PopoverPrimitive.Close asChild>
                <Link to="/services">{t("shell:status.allServices")}</Link>
              </PopoverPrimitive.Close>
            ) : null}
            <PopoverPrimitive.Close asChild>
              <Link to="/incidents">{t("shell:status.allIncidents")}</Link>
            </PopoverPrimitive.Close>
          </footer>
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}
