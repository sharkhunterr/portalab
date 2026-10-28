import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { useJudge, useVerdict, type Verdict } from "./api";
import "./taste.css";

export const VERDICTS: { verdict: Verdict; icon: string }[] = [
  { verdict: "like", icon: "thumbs-up" },
  { verdict: "dislike", icon: "thumbs-down" },
  { verdict: "seen", icon: "eye" },
  { verdict: "later", icon: "bookmark" },
];

/**
 * Issue 190: on a title's page, what I think of it — « I like it », « not for me », « seen », « later ».
 * One at a time; pressing the chosen one again takes it back. An episode's goes to its series.
 */
export function TasteButtons({ objectId, title }: { objectId: string; title: string }) {
  const t = useT();
  const current = useVerdict(objectId);
  const judge = useJudge();
  const chosen = judge.isPending ? judge.variables?.verdict : current.data;
  return (
    <fieldset className="media-taste" aria-label={t("media:taste.about", { title })}>
      {VERDICTS.map(({ verdict, icon }) => {
        const on = chosen === verdict;
        return (
          <button
            key={verdict}
            type="button"
            className="media-taste__button"
            data-verdict={verdict}
            aria-pressed={on}
            disabled={current.isPending}
            onClick={() => judge.mutate({ objectId, verdict: on ? null : verdict })}
          >
            <Icon name={icon} size={16} />
            <span>{t(`media:taste.verdict.${verdict}`)}</span>
          </button>
        );
      })}
    </fieldset>
  );
}
