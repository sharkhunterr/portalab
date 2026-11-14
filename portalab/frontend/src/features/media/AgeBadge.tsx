import { useT } from "../../i18n/hooks/useT";

/** The colour band of an age: all ages, 7, 12, 16, 18 (as the rating boards draw them). */
export function ageTier(age: number): string {
  if (age < 0) return "unknown"; // unrated
  if (age >= 18) return "18";
  if (age >= 16) return "16";
  if (age >= 12) return "12";
  if (age >= 7) return "7";
  return "all";
}

/**
 * Issue 434: a title's age rating, as a badge coloured by age — the strictest of its ratings (each one in its
 * tooltip). ``compact`` on a poster.
 */
export function AgeBadge({
  age,
  sources,
  compact = false,
}: {
  age: number | null | undefined;
  sources?: string | null;
  compact?: boolean;
}) {
  const t = useT();
  if (age === null || age === undefined) return null;
  const unrated = age < 0; // issue 434: « ? » for a title without any rating
  const label = unrated ? t("media:age.unknown") : age <= 3 ? t("media:age.all") : `${age}+`;
  const said = unrated ? t("media:age.unrated") : t("media:age.label", { age: age <= 3 ? 0 : age });
  return (
    <span
      className="age-badge"
      data-tier={ageTier(age)}
      data-compact={compact || undefined}
      title={sources ? `${said} — ${sources}` : said}
    >
      <span aria-hidden="true">{label}</span>
      <span className="visually-hidden">{said}</span>
    </span>
  );
}
