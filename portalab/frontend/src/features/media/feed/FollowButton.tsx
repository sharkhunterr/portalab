import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { type FollowKind, useFollows, useFollowToggle } from "./api";
import "./feed.css";

/**
 * #299: « Suivre » on a person's or a series' page — what it brings lands in « Mon fil ». Private: nobody
 * else ever sees what I follow. Pressing it again stops following.
 */
export function FollowButton({ kind, value, name }: { kind: FollowKind; value: string; name: string }) {
  const t = useT();
  const follows = useFollows();
  const toggle = useFollowToggle();
  const folded = name.toLocaleLowerCase();
  const current = (follows.data ?? []).find(
    (f) => f.kind === kind && (f.ref === value || f.label.toLocaleLowerCase() === folded),
  );
  const on = toggle.isPending ? Boolean(toggle.variables?.on) : Boolean(current);
  return (
    <button
      type="button"
      className="media-follow"
      aria-pressed={on}
      disabled={follows.isPending || toggle.isPending}
      title={t("media:follow.hint", { name })}
      onClick={() => toggle.mutate({ kind, ref: current?.ref ?? value, on: !on })}
    >
      <Icon name={on ? "check" : "plus"} size={16} />
      <span>{t(on ? "media:follow.following" : "media:follow.follow")}</span>
    </button>
  );
}
