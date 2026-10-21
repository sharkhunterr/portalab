import { type CSSProperties, useEffect, useState } from "react";
import { Link } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";

/** The time now, again every ``every`` ms (what « in 3 hours » and a progress bar are measured against). */
export function useNow(every = 60_000): number {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), every);
    return () => window.clearInterval(timer);
  }, [every]);
  return now;
}

/** The start and the end, apart from the text: « 21 Oct · 16:22 → 18:22 » (the end's day when another). */
function When({ starts, ends }: { starts: string; ends?: string | null | undefined }) {
  const t = useT();
  const format = useFormat();
  const day = (at: string) => {
    const { day, month } = format.dayMonth(at);
    return `${day} ${month}`;
  };
  const sameDay = ends ? day(starts) === day(ends) : true;
  return (
    <span className="status-banner__when">
      <Icon name="calendar" size={14} />
      <time dateTime={starts} title={`${t("support:banner.starts")} · ${format.dateTime(starts)}`}>
        {day(starts)} · {format.time(starts)}
      </time>
      {ends ? (
        <>
          <span aria-hidden="true">→</span>
          <time dateTime={ends} title={`${t("support:banner.ends")} · ${format.dateTime(ends)}`}>
            {sameDay ? format.time(ends) : `${day(ends)} · ${format.time(ends)}`}
          </time>
        </>
      ) : null}
    </span>
  );
}

/**
 * 027: a maintenance, an incident or an announcement told across the portal — a compact tinted card: its
 * icon, what it is and when (« Maintenance · ends in 2 hours ») with its title, a line of details under
 * them, the start and end apart in a chip, a link to the details and a close button; a running window shows
 * how far along it is along its bottom edge. On a phone the dates go under the title. An announcement may
 * have no dates nor link, and a critical one cannot be closed.
 */
export function StatusBanner({
  tone,
  icon,
  eyebrow,
  title,
  text,
  starts,
  ends,
  progress,
  details,
  detailsLabel,
  onClose,
}: {
  tone: "planned" | "running" | "incident" | "info" | "success" | "warning" | "critical";
  icon: string;
  eyebrow: string[];
  title: string;
  text?: string | null | undefined;
  starts?: string | null | undefined;
  ends?: string | null | undefined;
  progress?: number | null | undefined;
  details?: string | null | undefined;
  detailsLabel?: string;
  onClose?: (() => void) | undefined;
}) {
  const t = useT();
  return (
    <section className="status-banner" data-tone={tone} role="status" aria-label={title}>
      <div className="status-banner__inner">
        <span className="status-banner__icon" aria-hidden="true">
          <Icon name={icon} size={14} />
        </span>
        <div className="status-banner__body">
          <p className="status-banner__head">
            <span className="status-banner__eyebrow">{eyebrow.filter(Boolean).join(" · ")}</span>
            <strong className="status-banner__title">{title}</strong>
          </p>
          {text ? (
            <p className="status-banner__text" title={text}>
              {text}
            </p>
          ) : null}
        </div>
        {starts ? <When starts={starts} ends={ends} /> : null}
        {details ? (
          <Link to={details} className="status-banner__details">
            {detailsLabel ?? t("support:banner.details")}
            <Icon name="chevron-right" size={14} />
          </Link>
        ) : null}
        {onClose ? (
          <button
            type="button"
            className="status-banner__close"
            onClick={onClose}
            aria-label={t("support:banner.close")}
            title={t("support:banner.close")}
          >
            <Icon name="close" size={12} />
          </button>
        ) : null}
      </div>
      {progress != null ? (
        <span
          className="status-banner__progress"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(progress * 100)}
          aria-label={t("support:banner.progress")}
          style={{ "--progress": Math.min(1, Math.max(0, progress)) } as CSSProperties}
        >
          <span />
        </span>
      ) : null}
    </section>
  );
}
