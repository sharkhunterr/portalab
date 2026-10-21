import * as PopoverPrimitive from "@radix-ui/react-popover";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router";
import { api } from "../../api/client";
import { systemPrefersReducedMotion } from "../../design-system/a11y/motion";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { useNavigationView } from "../nav/NavigationProvider";
import {
  ANNOUNCEMENT_ICONS,
  type AnnouncementTone,
  announcementTone,
  DAY,
  isRunning,
  upcoming,
  useAnnouncementBanners,
  useMaintenances,
  useOpenIncidents,
} from "../status/portalStatus";
import { useNow } from "../status/StatusBanner";

const WEEK = 7 * DAY;
const ICONS = {
  ok: "heart",
  incident: "alert",
  maintenance: "wrench",
  degraded: "warning",
  announcement: "megaphone",
  planned: "wrench",
} as const;
type State = keyof typeof ICONS;
// the strongest tone among the announcements gives the icon and its colour
const TONE_RANK: AnnouncementTone[] = ["critical", "warning", "success", "info"];
// how long each signal stays when the icon goes round them: the first (the most serious) twice as long
const STEP = 2400;

interface Signal {
  state: State;
  count: number;
  label: string;
  icon: string;
  tone?: AnnouncementTone;
}

function motionReduced(): boolean {
  return document.documentElement.dataset.motion === "none" || systemPrefersReducedMotion();
}

/** Which signal the button shows now: the first, then each in turn when there are several. */
function useTurn(length: number): number {
  const [turn, setTurn] = useState(0);
  useEffect(() => {
    if (length < 2 || motionReduced()) {
      setTurn(0);
      return;
    }
    const at = turn % length;
    const timer = window.setTimeout(() => setTurn((at + 1) % length), at === 0 ? STEP * 2 : STEP);
    return () => window.clearTimeout(timer);
  }, [turn, length]);
  return length ? turn % length : 0;
}

/**
 * 027: the control center — the portal's state at a glance in the header: a heart beating while all is
 * well, the danger sign during an incident, a wrench during (or the day before) a maintenance, a warning
 * when services are in trouble, a megaphone in the announcement's colour while one is shown, with how many.
 * When several are going on at once, the icon goes round them, the most serious first and longest (just
 * the most serious when motion is reduced). Pressed, a small window under it tells the details: the open
 * incidents (severity, step, since when), the maintenances of the week (running or when), the
 * announcements shown (even those a member closed), the services in trouble, and the way to the status and
 * incidents pages.
 */
export function ControlCenterButton() {
  const t = useT();
  const format = useFormat();
  const now = useNow();
  const { view } = useNavigationView();
  const canRead = view.groups.some((g) => g.entries.some((e) => e.key === "health.services"));
  const open = useOpenIncidents();
  const windows = useMaintenances();
  const banners = useAnnouncementBanners();
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
  const announcements = Array.isArray(banners.data) ? banners.data : [];
  const items = Array.isArray(services.data) ? services.data : [];
  // services whose alerting rule leaves them out of the portal's health (internal ones) do not count
  const troubled = items.filter(
    (s) => s.degrades_portal !== false && (s.state === "unavailable" || s.state === "degraded"),
  ).length;
  const strongest =
    TONE_RANK.find((tone) => announcements.some((a) => announcementTone(a.tone) === tone)) ?? "info";
  const signals: Signal[] = [
    incidents.length
      ? {
          state: "incident",
          count: incidents.length,
          label: t("shell:incidents", { count: incidents.length }),
        }
      : null,
    running.length
      ? {
          state: "maintenance",
          count: running.length,
          label: t("shell:status.maintenanceRunning", { count: running.length }),
        }
      : null,
    troubled
      ? { state: "degraded", count: troubled, label: t("shell:health.degraded", { count: troubled }) }
      : null,
    announcements.length
      ? {
          state: "announcement",
          count: announcements.length,
          label: t("shell:status.announcementsShown", { count: announcements.length }),
          tone: strongest,
        }
      : null,
    soon.length
      ? {
          state: "planned",
          count: soon.length,
          label: t("shell:status.maintenancePlanned", { count: soon.length }),
        }
      : null,
  ]
    .filter((s): s is Omit<Signal, "icon"> => s !== null)
    .map((s) => ({ ...s, icon: s.tone ? ANNOUNCEMENT_ICONS[s.tone] : ICONS[s.state] }));
  const turn = useTurn(signals.length);
  if (!incidents.length && !week.length && !announcements.length && !items.length) return null;
  const ok: Signal = { state: "ok", count: 0, label: t("shell:health.ok"), icon: ICONS.ok };
  const top = signals[0] ?? ok;
  const shown = signals[turn] ?? ok;
  const label = signals.length ? signals.map((s) => s.label).join(" · ") : ok.label;
  return (
    <PopoverPrimitive.Root>
      <PopoverPrimitive.Trigger asChild>
        <button
          type="button"
          className="ds-button ds-button--ghost ds-button--icon shell-health"
          data-state={shown.state}
          data-tone={shown.tone}
          data-turns={signals.length > 1 ? "true" : undefined}
          aria-label={label}
          title={label}
        >
          {/* a new key on each turn: the icon comes in again */}
          <span className="shell-health__glyph" key={`${shown.state}-${turn}`}>
            <Icon name={shown.icon} />
          </span>
          {shown.count ? (
            <span className="shell-health__count" aria-hidden="true">
              {shown.count > 99 ? "99+" : shown.count}
            </span>
          ) : null}
        </button>
      </PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          className="ds-popover shell-status"
          data-state-tone={top.state}
          data-tone={top.tone}
          aria-label={t("shell:status.title")}
          sideOffset={6}
          align="end"
          collisionPadding={12}
        >
          <p className="shell-status__head">
            <span className="shell-status__badge" aria-hidden="true">
              <Icon name={top.icon} size={18} />
            </span>
            <span>
              <small>{t("shell:status.title")}</small>
              <strong>{top.label}</strong>
              {signals.length > 1 ? (
                <span className="shell-status__also">
                  {signals
                    .slice(1)
                    .map((s) => s.label)
                    .join(" · ")}
                </span>
              ) : null}
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

          {announcements.length ? (
            <section className="shell-status__group">
              <h3>{t("shell:status.announcements")}</h3>
              <ul>
                {announcements.map((a) => {
                  const tone = announcementTone(a.tone);
                  const content = (
                    <>
                      <span className="shell-status__dot" aria-hidden="true" />
                      <span className="shell-status__text">
                        <strong>{a.title}</strong>
                        <small>
                          {[
                            a.body ? a.body.split("\n")[0] : null,
                            a.banner_until
                              ? t("shell:status.until", { when: format.dateTime(a.banner_until) })
                              : null,
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                        </small>
                      </span>
                    </>
                  );
                  return (
                    <li key={a.id}>
                      {a.link ? (
                        <PopoverPrimitive.Close asChild>
                          <Link to={a.link} className="shell-status__item" data-tone={tone}>
                            {content}
                            <Icon name="chevron-right" size={14} />
                          </Link>
                        </PopoverPrimitive.Close>
                      ) : (
                        <div className="shell-status__item" data-tone={tone}>
                          {content}
                        </div>
                      )}
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
