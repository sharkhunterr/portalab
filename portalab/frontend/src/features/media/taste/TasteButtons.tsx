import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { useJudge, useVerdict, type Verdict } from "./api";
import "./taste.css";

export const VERDICTS: { verdict: Verdict; icon: string }[] = [
  { verdict: "like", icon: "thumbs-up" },
  { verdict: "dislike", icon: "thumbs-down" },
  { verdict: "later", icon: "bookmark" },
];

/**
 * Issue 190: on a title's page, what I think of it — « I like it », « not for me », « later » (what I saw,
 * read or played, the services tell).
 * One at a time; pressing the chosen one again takes it back. An episode's goes to its series.
 */
export function TasteButtons({
  objectId,
  title,
  compact = false,
}: {
  objectId: string;
  title: string;
  /** a title's head: three icons in its action bar (their names as tooltips), issue 355 */
  compact?: boolean;
}) {
  const t = useT();
  const current = useVerdict(objectId);
  const judge = useJudge();
  const chosen = judge.isPending ? judge.variables?.verdict : current.data;
  return (
    <fieldset
      className={compact ? "media-taste media-taste--compact" : "media-taste"}
      aria-label={t("media:taste.about", { title })}
    >
      {VERDICTS.map(({ verdict, icon }) => {
        const on = chosen === verdict;
        const name = t(`media:taste.verdict.${verdict}`);
        return (
          <button
            key={verdict}
            type="button"
            className={compact ? "media-action media-action--icon" : "media-taste__button"}
            data-verdict={verdict}
            aria-pressed={on}
            title={compact ? name : undefined}
            disabled={current.isPending}
            onClick={() => judge.mutate({ objectId, verdict: on ? null : verdict })}
          >
            <Icon name={icon} size={16} />
            <span className={compact ? "visually-hidden" : undefined}>{name}</span>
          </button>
        );
      })}
    </fieldset>
  );
}
