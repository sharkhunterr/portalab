/**
 * #98 — a small badge with a number: something waits there (a purchase to validate, a proposal to
 * moderate…). Nothing is drawn at zero; past 99 it reads « 99+ ». ``dot`` draws the badge alone, without
 * its number (an icon rail, where room is short); the number is always told to assistive technologies.
 */
export function CountBadge({
  count,
  label,
  dot = false,
}: {
  count: number;
  /** What the number means, read out (« 2 to handle »). */
  label?: string | undefined;
  dot?: boolean | undefined;
}) {
  if (!count || count < 1) return null;
  const shown = count > 99 ? "99+" : String(count);
  return (
    <span className="count-badge" data-dot={dot || undefined} role="status" aria-label={label ?? shown}>
      {dot ? null : <span aria-hidden="true">{shown}</span>}
    </span>
  );
}
