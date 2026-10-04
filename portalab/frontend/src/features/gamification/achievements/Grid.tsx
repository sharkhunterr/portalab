import { useMemo, useState } from "react";
import { ProgressBar } from "../../../design-system/components/Badges";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import type { AchievementView } from "../api";

/**
 * Achievements (spec 013 T026, 027 US9), like a game platform: completion summary, category filter, sort by
 * rarity / recent / name, and for each achievement its category, the share of members who unlocked it and the
 * rarity derived from it. Locked / hidden / unlocked are stated in **text** (never color alone); rare unlocked
 * medals are animated (static under reduced motion). Hidden achievements keep their secret but show rarity.
 */
const RANK: Record<string, number> = { legendary: 0, epic: 1, rare: 2, common: 3 };
type Sort = "rarity" | "recent" | "name";

export function AchievementGrid({ achievements }: { achievements: AchievementView[] }) {
  const t = useT();
  const format = useFormat();
  const [category, setCategory] = useState("");
  const [sort, setSort] = useState<Sort>("rarity");
  const unlocked = achievements.filter((a) => a.state === "unlocked").length;
  const categories = [...new Set(achievements.map((a) => a.category).filter(Boolean))] as string[];
  const shown = useMemo(() => {
    const list = achievements.filter((a) => !category || a.category === category);
    return [...list].sort((a, b) => {
      if (sort === "recent") return (b.unlocked_at ?? "").localeCompare(a.unlocked_at ?? "");
      if (sort === "name") return (a.label ?? "~").localeCompare(b.label ?? "~");
      return (
        (RANK[a.rarity ?? "common"] ?? 3) - (RANK[b.rarity ?? "common"] ?? 3) ||
        (a.unlock_share ?? 0) - (b.unlock_share ?? 0)
      );
    });
  }, [achievements, category, sort]);
  return (
    <section aria-labelledby="gamification-achievements" className="achievements">
      <header className="achievements__head">
        <h2 id="gamification-achievements">{t("gamification:achievements.title")}</h2>
        <div className="achievements__summary">
          <span>{t("gamification:achievements.summary", { unlocked, total: achievements.length })}</span>
          <ProgressBar
            value={achievements.length ? unlocked / achievements.length : 0}
            label={t("gamification:achievements.summary", { unlocked, total: achievements.length })}
          />
        </div>
      </header>
      <div className="achievements__toolbar">
        {categories.length > 1 ? (
          <fieldset className="ds-subnav" aria-label={t("gamification:achievements.title")}>
            <button type="button" aria-pressed={!category} onClick={() => setCategory("")}>
              {t("gamification:achievements.all")}
            </button>
            {categories.map((c) => (
              <button key={c} type="button" aria-pressed={category === c} onClick={() => setCategory(c)}>
                {t(`gamification:achievements.category.${c}`)}
              </button>
            ))}
          </fieldset>
        ) : null}
        <label className="achievements__sort">
          {t("gamification:achievements.sort")}
          <select value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
            {(["rarity", "recent", "name"] as const).map((value) => (
              <option key={value} value={value}>
                {t(`gamification:achievements.sort.${value}`)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <ul className="gamification-grid achievements__list">
        {shown.map((achievement) => {
          const rarity = achievement.rarity ?? "common";
          const share = achievement.unlock_share ?? 0;
          return (
            <li
              key={achievement.key}
              className="ds-card achievement"
              data-state={achievement.state}
              data-rarity={rarity}
            >
              <span className="achievement__medal" aria-hidden="true">
                <Icon
                  name={achievement.state === "hidden" ? "lock" : (achievement.icon ?? "trophy")}
                  size={26}
                />
              </span>
              <div className="achievement__body">
                {achievement.state === "hidden" ? (
                  <h3>{t("gamification:achievements.hidden")}</h3>
                ) : (
                  <>
                    <h3>{achievement.label}</h3>
                    {achievement.description ? <p>{achievement.description}</p> : null}
                    {achievement.category ? (
                      <span className="achievement__category">
                        {t(`gamification:achievements.category.${achievement.category}`)}
                      </span>
                    ) : null}
                    {achievement.state === "locked"
                      ? (achievement.progress ?? []).map((step, index) => (
                          // biome-ignore lint/suspicious/noArrayIndexKey: criteria are positional
                          <span key={index} className="achievement__step">
                            <ProgressBar
                              value={step.target ? step.current / step.target : 0}
                              label={t("gamification:achievements.progress", step)}
                              size="sm"
                              tone="accent"
                            />
                            <span className="gamification-meta">
                              {t("gamification:achievements.progress", step)}
                            </span>
                          </span>
                        ))
                      : null}
                  </>
                )}
              </div>
              <div className="achievement__meta">
                {achievement.state === "hidden" ? null : (
                  <span className="ds-badge">{t(`gamification:achievements.${achievement.state}`)}</span>
                )}
                <span className="achievement__rarity">{t(`gamification:achievements.rarity.${rarity}`)}</span>
                <span className="achievement__share">
                  {t("gamification:achievements.share", { share: format.number(share) })}
                </span>
                {achievement.unlocked_at ? (
                  <span className="gamification-meta">
                    {t("gamification:achievements.unlockedOn", {
                      date: format.date(achievement.unlocked_at),
                    })}
                  </span>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
