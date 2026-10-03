import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import type { Progression } from "../api";

/**
 * Progression card (spec 013 T024): the Level derives from XP (progress bar toward the next level);
 * XP, Contribution and Coins are always shown **separately** — never as one score, never converted.
 */
export function ProgressionCard({ progression }: { progression: Progression }) {
  const t = useT();
  const format = useFormat();
  const next = progression.next_level_at;
  const span = next === null ? 1 : Math.max(1, next - progression.level_floor);
  const done = next === null ? span : progression.xp - progression.level_floor;
  return (
    <section className="ds-card gamification-card" aria-labelledby="gamification-level">
      <h2 id="gamification-level">{t("gamification:level", { level: progression.level })}</h2>
      <progress
        max={span}
        value={Math.min(done, span)}
        aria-labelledby="gamification-level gamification-next"
      />
      <p id="gamification-next" className="gamification-meta">
        {next === null
          ? t("gamification:progression.max")
          : t("gamification:progression.next", {
              remaining: next - progression.xp,
              next: progression.level + 1,
            })}
      </p>
      <dl className="gamification-values">
        <div>
          <dt>{t("gamification:value.xp")}</dt>
          <dd>{format.number(progression.xp)}</dd>
        </div>
        <div>
          <dt>{t("gamification:value.contribution")}</dt>
          <dd>{format.number(progression.contribution)}</dd>
        </div>
        <div>
          <dt>{t("gamification:value.coins")}</dt>
          <dd>{format.number(progression.coins)}</dd>
        </div>
      </dl>
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
