import { useEffect, useState } from "react";
import { useGpuLook } from "../visuals/gpu";
import { FxLayer } from "./Fx";
import { Icon } from "./Icon";

/** The look worn on the profile, as set on ``<html data-level-badge>`` (followed when it changes). */
function useWornLevelLook(): string | undefined {
  const [worn, setWorn] = useState(() =>
    typeof document === "undefined" ? undefined : document.documentElement.dataset.levelBadge,
  );
  useEffect(() => {
    const root = document.documentElement;
    const observer = new MutationObserver(() => setWorn(root.dataset.levelBadge));
    observer.observe(root, { attributes: true, attributeFilter: ["data-level-badge"] });
    setWorn(root.dataset.levelBadge);
    return () => observer.disconnect();
  }, []);
  return worn;
}

/**
 * Progression badges (spec 027 FR-001/FR-007): level, XP progress and Coins. Values are display-only —
 * the economy is never computed here. Large numbers use compact notation with the exact value in the
 * accessible name.
 */

export function compactNumber(value: number, locale?: string): string {
  if (Math.abs(value) < 10_000) return new Intl.NumberFormat(locale).format(value);
  return new Intl.NumberFormat(locale, { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

/** Share of the current level already earned, in [0, 1]; a top level (no next threshold) is full. */
export function levelProgress(xp: number, floor: number, next: number | null): number {
  if (next === null || next <= floor) return 1;
  return Math.min(1, Math.max(0, (xp - floor) / (next - floor)));
}

/**
 * 027: the rank of a level — the classic badge changes every ten levels (bronze, silver, gold, emerald,
 * sapphire, amethyst, ruby, then legend from level 100 and mythic from 250), like game platforms.
 */
export function levelTier(level: number): number {
  if (level >= 250) return 9;
  if (level >= 100) return 8;
  return Math.min(7, Math.floor(Math.max(0, level) / 10) + 1);
}

/** The member's level — a star tells it is a level, not a count (027). Its look is the one the member
 * wears (their profile's ``level`` slot, everyone sees it); ``look`` forces one (previews, other members). */
export function LevelBadge({
  level,
  label,
  look,
}: {
  level: number;
  label: string;
  look?: string | null | undefined;
}) {
  const worn = useWornLevelLook();
  const shown = look ?? worn;
  const gpu = useGpuLook("level_badge", shown); // 028: its pack's (Portalab's own included)
  const fx = gpu?.effect;
  return (
    <span
      className="ds-level"
      role="img"
      aria-label={label}
      data-look={shown ?? undefined}
      data-fx={fx}
      data-fx-cycle={gpu?.cycle || undefined}
      data-tier={levelTier(level)}
    >
      {fx ? <FxLayer effect={fx} cycle={gpu?.cycle} className="ds-level__fx" /> : null}
      <Icon name={levelTier(level) >= 8 ? "crown" : "star"} size={11} />
      <span aria-hidden="true">{level}</span>
    </span>
  );
}

export interface ProgressBarProps {
  value: number;
  /** Accessible name, e.g. "Level 3: 240 of 400 XP". */
  label: string;
  tone?: "xp" | "accent";
  size?: "sm" | "md";
}

export function ProgressBar({ value, label, tone = "xp", size = "md" }: ProgressBarProps) {
  const percent = Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <span
      className={`ds-bar ds-bar--${tone} ds-bar--${size}`}
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent}
    >
      <span className="ds-bar__fill" style={{ inlineSize: `${percent}%` }} />
    </span>
  );
}

export function CoinBadge({ amount, label, locale }: { amount: number; label: string; locale?: string }) {
  const exact = new Intl.NumberFormat(locale).format(amount);
  return (
    <span className="ds-coins" role="img" aria-label={`${label}: ${exact}`} title={exact}>
      <Icon name="coins" size={18} />
      <span aria-hidden="true">{compactNumber(amount, locale)}</span>
    </span>
  );
}
