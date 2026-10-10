import { LevelBadge, levelProgress, ProgressBar } from "../../../design-system/components/Badges";
import { StatFigure } from "../../../design-system/components/Collections";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import type { Progression } from "../api";
import { GainsNow } from "../boost";

/**
 * Progression card (spec 013 T024): the Level derives from XP (progress bar toward the next level);
 * XP, Contribution and Coins are always shown **separately** — never as one score, never converted.
 */
export function ProgressionCard({ progression }: { progression: Progression }) {
  const t = useT();
  const format = useFormat();
  const next = progression.next_level_at;
  const levelLabel = t("gamification:level", { level: progression.level });
  return (
    <section className="ds-card gamification-card" aria-labelledby="gamification-level">
      <div className="gamification-hero">
        <LevelBadge level={progression.level} label={levelLabel} />
        <div className="gamification-hero__text">
          <h2 id="gamification-level">{levelLabel}</h2>
          <ProgressBar
            value={levelProgress(progression.xp, progression.level_floor, next ?? null)}
            label={levelLabel}
          />
          <GainsNow />
        </div>
      </div>
      <p id="gamification-next" className="gamification-meta">
        {next === null
          ? t("gamification:progression.max")
          : t("gamification:progression.next", {
              remaining: next - progression.xp,
              next: progression.level + 1,
            })}
      </p>
      <div className="gamification-values">
        <StatFigure icon="zap" label={t("gamification:value.xp")} value={format.number(progression.xp)} />
        <StatFigure
          icon="heart"
          label={t("gamification:value.contribution")}
          value={format.number(progression.contribution)}
        />
        <StatFigure
          icon="coins"
          label={t("gamification:value.coins")}
          value={format.number(progression.coins)}
        />
      </div>
      {progression.reserved_coins ? (
        <p className="gamification-meta">
          {t("gamification:progression.reserved", { amount: progression.reserved_coins })}
        </p>
      ) : null}
      <p className="gamification-meta">
        {t("gamification:progression.achievements", { count: progression.achievements })}
      </p>
    </section>
  );
}
