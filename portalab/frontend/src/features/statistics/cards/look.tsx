import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import type { StatResult } from "../api";

/** Issue 481: each statistic's icon, as My media gives its figures one — by key, else by domain. */
const ICONS: Record<string, string> = {
  "trends.active_members": "users",
  "trends.titles_finished": "film",
  "trends.requests": "inbox",
  "trends.xp_earned": "sparkles",
  "trends.xp_granted": "gift",
  "trends.achievements_unlocked": "trophy",
  "activity.my_visits": "calendar",
  "activity.visits": "calendar",
  "users.my_sign_ins": "key",
  "users.active_by_day": "users",
  "gamification.coins_earned": "coins",
  "gamification.level_ups": "trending",
  "gamification.rewards_by_source": "gift",
  "gamification.achievements_unlocked": "trophy",
  "marketplace.coins_spent": "shop",
  "marketplace.purchases": "shop",
  "media.catalog_added": "film",
  "services.health_changes": "server",
  "playback.community_viewers": "film",
  "support.feedback_received": "message",
};
const DOMAIN_ICONS: Record<string, string> = {
  activity: "activity",
  community: "heart",
  gamification: "star",
  gaming: "game",
  marketplace: "shop",
  requests: "inbox",
  support: "ticket",
  users: "user",
  playback: "film",
  media: "film",
};

export function statIcon(key: string, domain: string): string {
  return ICONS[key] ?? DOMAIN_ICONS[domain] ?? "chart";
}

/**
 * Issue 481: a statistic's change as My media tells it — an arrow, coloured, and the share of change versus
 * the previous period; « new » when nothing came before; « no comparison » when the statistic did not cover
 * the previous period yet (issue 479). The full sentence stays for screen readers.
 */
export function TrendBadge({ result }: { result: StatResult }) {
  const t = useT();
  const format = useFormat();
  const trend = result.trend;
  if (result.value === null) return null;
  if (!trend) {
    return (
      <span className="stat-trend" data-trend="none" title={t("statistics:trend.none")}>
        <Icon name="minus" size={14} />
        {t("statistics:badge.none")}
      </span>
    );
  }
  const fresh = trend.direction === "up" && trend.percent === null;
  const sentence = fresh
    ? t("statistics:trend.new")
    : t(`statistics:trend.${trend.direction}`, {
        delta: format.number(Math.abs(trend.delta)),
        percent: trend.percent === null ? "—" : format.percent(Math.abs(trend.percent) / 100),
      });
  const label = fresh
    ? t("statistics:badge.new")
    : trend.direction === "flat"
      ? t("statistics:badge.flat")
      : t("statistics:badge.change", {
          value:
            trend.percent === null
              ? format.number(Math.abs(trend.delta))
              : format.percent(Math.abs(trend.percent) / 100),
        });
  return (
    <span className="stat-trend" data-trend={fresh ? "new" : trend.direction} title={sentence}>
      <Icon
        name={trend.direction === "up" ? "arrow-up" : trend.direction === "down" ? "arrow-down" : "minus"}
        size={14}
      />
      <span aria-hidden="true">{label}</span>
      <span className="visually-hidden">{sentence}</span>
    </span>
  );
}
