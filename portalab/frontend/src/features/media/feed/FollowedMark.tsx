import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import "./feed.css";

/** #299: « followed » — a small badge on a person's portrait, a chip or a name I follow (said in words to
 * assistive technologies, never by its colour alone). ``on``: over a portrait's corner. */
export function FollowedMark({ on = false }: { on?: boolean }) {
  const t = useT();
  return (
    <span className="followed-mark" data-on={on || undefined} title={t("media:follow.following")}>
      <Icon name="check" size={on ? 14 : 12} />
      <span className="visually-hidden">{t("media:follow.following")}</span>
    </span>
  );
}
