import { Link } from "react-router";
import { CoinBadge, LevelBadge, levelProgress, ProgressBar } from "../../design-system/components/Badges";
import type { Progression } from "../../features/gamification/api";
import { useT } from "../../i18n/hooks/useT";
import { useLocaleContext } from "../../i18n/provider/I18nProvider";
import { useShellStrings } from "../strings";

/**
 * Level + XP progress and Coins in the header (spec 027 FR-001/006). Display-only: the values come from the
 * server's progression; nothing is computed beyond the progress ratio. Absent when gamification is off or
 * unavailable — the space collapses, other header elements are unaffected.
 */
export function ProgressChip({
  progression,
  compact = false,
  coins = true,
}: {
  progression: Progression;
  compact?: boolean;
  /** 027: whether Coins show beside the level (always in the header, phones included) */
  coins?: boolean;
}) {
  const t = useT();
  const strings = useShellStrings();
  const { locale } = useLocaleContext();
  const { level, xp, level_floor: floor, next_level_at: next } = progression;
  const ratio = levelProgress(xp, floor, next ?? null);
  const progressLabel =
    next === null || next === undefined
      ? t("shell:levelMax", { level })
      : t("shell:levelProgress", { level, xp: xp - floor, next: next - floor });
  return (
    <div className="shell-progress" data-compact={compact ? "true" : undefined}>
      <Link to="/progression" className="shell-progress__level" aria-label={progressLabel}>
        <LevelBadge level={level} label={t("shell:levelLabel", { level })} />
        {compact ? null : (
          <span className="shell-progress__bar">
            <ProgressBar value={ratio} label={progressLabel} size="sm" />
          </span>
        )}
      </Link>
      {coins ? (
        <Link to="/progression" className="shell-progress__coins">
          <CoinBadge amount={progression.coins} label={strings.coins} locale={locale} />
        </Link>
      ) : null}
    </div>
  );
}
