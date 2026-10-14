import { Link } from "react-router";
import { useT } from "../../../i18n/hooks/useT";
import { useAchievements } from "../../gamification/api";

const KNOWN = new Set(["achievement.unlocked", "user.level_up", "quest.completed", "project.created"]);

/** The icon of a feed entry's kind (027). */
export const FEED_ICONS: Record<string, string> = {
  "achievement.unlocked": "trophy",
  "user.level_up": "arrow-up",
  "quest.completed": "target",
  "project.created": "lightbulb",
};

/** The avatar of a feed entry's actor — none for an anonymous one (issue 120): the initials' « ? » only. */
export const actorAvatar = (item: { actor_id: string; anonymous?: boolean | null }) =>
  item.anonymous ? null : `/api/v1/users/${item.actor_id}/avatar`;

/** One feed entry as localized text (026): the stored key and parameters, the actor linking to the profile;
 * an achievement is named by its label (027), never by its technical key. An anonymous actor (issue 120)
 * is « an anonymous member », with no link. */
export function FeedText({
  kind,
  actorId,
  actorName,
  anonymous,
  params,
}: {
  kind: string;
  actorId: string;
  actorName: string | null | undefined;
  anonymous?: boolean | null | undefined;
  params: Record<string, unknown>;
}) {
  const t = useT();
  const achievements = useAchievements();
  const actor = anonymous ? t("community:feed.anonymous") : (actorName ?? t("community:feed.someone"));
  const key = KNOWN.has(kind) ? `community:feed.${kind}` : "community:feed.generic";
  const values = Object.fromEntries(
    Object.entries(params).filter(([, v]) => typeof v === "string" || typeof v === "number"),
  ) as Record<string, string | number>;
  if (kind === "achievement.unlocked" && typeof values.achievement === "string") {
    const known = Array.isArray(achievements.data) ? achievements.data : [];
    const found = known.find((a) => a.key === values.achievement);
    if (found) values.achievement = found.label ?? t("community:feed.hiddenAchievement"); // hidden: no name
  }
  const text = t(key, { ...values, actor: "\u0000" });
  const [before, after] = text.split("\u0000");
  return (
    <span>
      {before}
      {anonymous ? (
        <span className="community-anonymous">{actor}</span>
      ) : (
        <Link to={`/community/members/${actorId}`}>{actor}</Link>
      )}
      {after ?? ""}
    </span>
  );
}
