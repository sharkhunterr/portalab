import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import type { AchievementView } from "../api";

/** Achievements grid (spec 013 T026): locked / hidden / unlocked with **text** labels, not color alone. */
export function AchievementGrid({ achievements }: { achievements: AchievementView[] }) {
  const t = useT();
  const format = useFormat();
  return (
    <section aria-labelledby="gamification-achievements">
      <h2 id="gamification-achievements">{t("gamification:achievements.title")}</h2>
      <ul className="gamification-grid">
        {achievements.map((achievement) => (
          <li key={achievement.key} className="ds-card achievement" data-state={achievement.state}>
            <span className="achievement__medal" aria-hidden="true">
              <Icon name={achievement.state === "hidden" ? "lock" : "trophy"} size={26} />
            </span>
            {achievement.state === "hidden" ? (
              <p>{t("gamification:achievements.hidden")}</p>
            ) : (
              <>
                <h3>{achievement.label}</h3>
                <p className="ds-badge">{t(`gamification:achievements.${achievement.state}`)}</p>
                {achievement.description ? <p>{achievement.description}</p> : null}
                {achievement.unlocked_at ? (
                  <p className="gamification-meta">{format.date(achievement.unlocked_at)}</p>
                ) : null}
                {achievement.state === "locked"
                  ? (achievement.progress ?? []).map((step, index) => (
                      // biome-ignore lint/suspicious/noArrayIndexKey: criteria are positional
                      <p key={index} className="gamification-meta">
                        {t("gamification:achievements.progress", step)}
                      </p>
                    ))
                  : null}
              </>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
