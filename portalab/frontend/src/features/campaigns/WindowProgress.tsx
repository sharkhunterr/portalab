import { useT } from "../../i18n/hooks/useT";

/** 027: how far through the running window we are — « day 7 of 23 » and a bar. */
export function WindowProgress({ start, end }: { start: string; end: string }) {
  const t = useT();
  const from = Date.parse(start);
  const to = Date.parse(end);
  const ratio = to > from ? Math.min(1, Math.max(0, (Date.now() - from) / (to - from))) : 0;
  const days = Math.max(1, Math.ceil((to - from) / 86_400_000));
  const day = Math.min(days, Math.max(1, Math.ceil((Date.now() - from) / 86_400_000)));
  const label = t("campaigns:page.dayOf", { day, days });
  return (
    <div className="campaign-progress">
      <span className="campaign-progress__label">{label}</span>
      <span
        className="campaign-progress__track"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(ratio * 100)}
      >
        <span style={{ inlineSize: `${ratio * 100}%` }} />
      </span>
    </div>
  );
}
