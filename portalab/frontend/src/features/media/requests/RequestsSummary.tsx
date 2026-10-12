import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import type { RequestQuota } from "../discover/api";
import type { RequestInsights } from "./api";
import { QuotaTiles } from "./QuotaSummary";

const GROUPS = ["available", "approved", "pending", "declined"] as const;

/**
 * The top of « My requests »: how many over the period (and the one before), where they stand as one bar
 * (available, in progress, waiting, declined) — then what I may still ask for (#3: films and series with
 * the request service's limits, bought requests, the shop). One card, readable on a phone.
 */
export function RequestsSummary({
  data,
  quota,
}: {
  data: RequestInsights;
  quota?: RequestQuota | undefined;
}) {
  const t = useT();
  const format = useFormat();
  const total = data.summary.total;
  const parts = GROUPS.map((group) => ({ group, count: data.summary[group] })).filter((p) => p.count > 0);
  return (
    <section className="requests-summary" aria-label={t("media:requests.title")}>
      <div className="requests-summary__count">
        <strong>{format.number(total)}</strong>
        <span>{t("media:myRequests.requests", { count: total })}</span>
        {data.previous_total !== null ? (
          <small>{t("media:myRequests.previousCount", { count: data.previous_total })}</small>
        ) : null}
      </div>
      {total ? (
        <div className="requests-summary__states">
          <span className="requests-summary__bar" aria-hidden="true">
            {parts.map((part) => (
              <span key={part.group} data-group={part.group} style={{ flexGrow: part.count, flexBasis: 0 }} />
            ))}
          </span>
          <ul className="requests-summary__legend">
            {parts.map((part) => (
              <li key={part.group} data-group={part.group}>
                <strong>{format.number(part.count)}</strong> {t(`media:myRequests.group.${part.group}`)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {quota ? (
        <div className="requests-summary__quota request-quota">
          <QuotaTiles quota={quota} />
        </div>
      ) : null}
    </section>
  );
}
