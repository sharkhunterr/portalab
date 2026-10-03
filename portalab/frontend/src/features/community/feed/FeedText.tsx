import { Link } from "react-router";
import { useT } from "../../../i18n/hooks/useT";

const KNOWN = new Set(["achievement.unlocked", "user.level_up", "quest.completed", "project.created"]);

/** One feed entry as localized text (026): the stored key and parameters, the actor linking to the profile. */
export function FeedText({
  kind,
  actorId,
  actorName,
  params,
}: {
  kind: string;
  actorId: string;
  actorName: string | null | undefined;
  params: Record<string, unknown>;
}) {
  const t = useT();
  const actor = actorName ?? t("community:feed.someone");
  const key = KNOWN.has(kind) ? `community:feed.${kind}` : "community:feed.generic";
  const values = Object.fromEntries(
    Object.entries(params).filter(([, v]) => typeof v === "string" || typeof v === "number"),
  ) as Record<string, string | number>;
  const text = t(key, { ...values, actor: "\u0000" });
  const [before, after] = text.split("\u0000");
  return (
    <span>
      {before}
      <Link to={`/community/members/${actorId}`}>{actor}</Link>
      {after ?? ""}
    </span>
  );
}
