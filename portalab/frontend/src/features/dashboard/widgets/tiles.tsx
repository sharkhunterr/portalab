import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { compactNumber } from "../../../design-system/components/Badges";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";
import { PROGRESSION_KEY } from "../../../shell/header/useHeaderData";
import type { Progression } from "../../gamification/api";
import { useUnreadCount } from "../../notifications/api";
import { useIncidents } from "../../support/incidents/api";
import { registerWidgetComponent, type WidgetProps } from "./registry";

/**
 * One-cell tiles (027): a shortcut — an icon that opens a page of the portal or a link of the member's
 * choice — and a single value (level, Coins, unread notifications, incidents, requests left…). Values are
 * read where the portal already shows them, so a tile and the header always agree.
 */
function ShortcutTile({ payload }: WidgetProps) {
  const t = useT();
  const data = (payload.data ?? {}) as {
    destination?: string;
    route?: string | null;
    href?: string | null;
    icon?: string;
    label?: string | null;
  };
  const label =
    data.label || t(`dashboard:widget.shortcut.config.destination.${data.destination ?? "media"}`);
  const body = (
    <>
      <span className="widget-tile__icon" aria-hidden="true">
        <Icon name={data.icon ?? "link"} size={24} />
      </span>
      <span className="widget-tile__label">{label}</span>
    </>
  );
  if (data.href) {
    return (
      <a className="widget-tile" href={data.href} target="_blank" rel="noreferrer">
        {body}
      </a>
    );
  }
  return (
    <Link className="widget-tile" to={data.route ?? "/"}>
      {body}
    </Link>
  );
}

const VALUES: Record<string, { icon: string; route: string }> = {
  level: { icon: "star", route: "/progression" },
  coins: { icon: "coins", route: "/progression" },
  contribution: { icon: "handshake", route: "/progression" },
  achievements: { icon: "trophy", route: "/progression" },
  unread: { icon: "bell", route: "/notifications" },
  incidents: { icon: "alert", route: "/incidents" },
  requests_left: { icon: "inbox", route: "/media/requests" },
};

function useValue(metric: string): number | null {
  const progression = useQuery({
    queryKey: PROGRESSION_KEY,
    enabled: ["level", "coins", "contribution", "achievements"].includes(metric),
    retry: false,
    staleTime: 60_000,
    queryFn: async () => (await api.GET("/api/v1/me/progression")).data as Progression,
  });
  const unread = useUnreadCount(metric === "unread");
  const incidents = useIncidents("open");
  const requests = useQuery({
    queryKey: ["media", "requests", "quota"],
    enabled: metric === "requests_left",
    retry: false,
    queryFn: async () =>
      ((await api.GET("/api/v1/me/media/requests")).data as unknown as {
        quota?: { base_remaining?: number | null; extra_units?: number | null };
      }) ?? {},
  });
  switch (metric) {
    case "level":
    case "coins":
    case "contribution":
    case "achievements": {
      const value = progression.data?.[metric];
      return typeof value === "number" ? value : null;
    }
    case "unread":
      return unread.data ?? null;
    case "incidents":
      return Array.isArray(incidents.data) ? incidents.data.length : null;
    case "requests_left": {
      const quota = requests.data?.quota;
      if (!quota || typeof quota.base_remaining !== "number") return null;
      return quota.base_remaining + (quota.extra_units ?? 0);
    }
    default:
      return null;
  }
}

function ValueTile({ payload }: WidgetProps) {
  const t = useT();
  const { locale } = useLocaleContext();
  const metric = String((payload.data as { metric?: string } | null)?.metric ?? "level");
  const meta = VALUES[metric] ?? VALUES.level;
  const value = useValue(metric);
  const label = t(`dashboard:widget.value.config.metric.${metric}`);
  return (
    <Link
      className="widget-tile widget-tile--value"
      to={meta?.route ?? "/"}
      data-metric={metric}
      data-alert={(metric === "incidents" || metric === "unread") && value ? true : undefined}
      aria-label={value === null ? label : `${label}: ${value}`}
    >
      <span className="widget-tile__value">
        <Icon name={meta?.icon ?? "gauge"} size={16} />
        {value === null ? "–" : compactNumber(value, locale)}
      </span>
      <span className="widget-tile__label">{label}</span>
    </Link>
  );
}

registerWidgetComponent("dashboard.shortcut", ShortcutTile);
registerWidgetComponent("dashboard.value", ValueTile);
