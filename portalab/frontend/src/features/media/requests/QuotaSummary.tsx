import { Link } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { type QuotaWindow, type RequestQuota, requestsLeft, useRequestQuota } from "../discover/api";
import "../discover/discover.css";

const SHOP = "/marketplace?type=quota";

const KIND_ICON = { movie: "film", tv: "tv" } as const;

function Window({ kind, window }: { kind: "movie" | "tv"; window: QuotaWindow }) {
  const t = useT();
  const format = useFormat();
  const label = t(`media:quota.kind.${kind}`);
  const limited = Boolean(window.limit);
  const left = Math.max(0, window.remaining ?? 0);
  return (
    <li className="request-quota__tile" data-restricted={window.restricted || undefined}>
      <span className="request-quota__label">
        <Icon name={KIND_ICON[kind]} size={14} />
        {label}
      </span>
      <strong className="request-quota__value">
        {limited
          ? t("media:quota.leftShort", { count: left, limit: window.limit ?? 0 })
          : t("media:quota.unlimited")}
      </strong>
      {limited && window.limit ? (
        <span
          className="request-quota__bar"
          role="progressbar"
          aria-label={label}
          aria-valuemin={0}
          aria-valuemax={window.limit}
          aria-valuenow={window.used}
        >
          <span style={{ inlineSize: `${Math.min(100, (window.used / window.limit) * 100)}%` }} />
        </span>
      ) : null}
      {limited ? (
        <small>
          {window.days ? t("media:quota.every", { days: window.days }) : t("media:quota.always")}
          {window.restricted && window.renews_at
            ? ` · ${t("media:quota.renews", { date: format.date(window.renews_at, "medium") })}`
            : ""}
        </small>
      ) : null}
    </li>
  );
}

/** #3: the tiles of my quota — films and series (the request service's), else the portal's own — and the
 * requests bought in the shop, with where to buy more. */
export function QuotaTiles({ quota }: { quota: RequestQuota }) {
  const t = useT();
  const service = quota.service;
  return (
    <>
      {service && service.linked && "movie" in service ? (
        <ul className="request-quota__list">
          <Window kind="movie" window={service.movie} />
          <Window kind="tv" window={service.tv} />
        </ul>
      ) : service && service.linked ? (
        <p className="request-quota__note">{t("media:quota.unavailable")}</p>
      ) : (
        <ul className="request-quota__list">
          <li className="request-quota__tile" data-restricted={quota.base_remaining <= 0 || undefined}>
            <span className="request-quota__label">
              <Icon name="inbox" size={14} />
              {t("media:quota.portal")}
            </span>
            <strong className="request-quota__value">
              {t("media:quota.leftShort", { count: quota.base_remaining, limit: quota.base_limit })}
            </strong>
            <small>{t(`media:quota.period.${quota.period}`)}</small>
          </li>
        </ul>
      )}
      <p className="request-quota__extra">
        <span>{t("media:quota.extra", { count: quota.extra_units })}</span>
        <Link to={SHOP}>
          <Icon name="shop" size={14} />
          {t("media:quota.buy")}
        </Link>
      </p>
      {service && !service.linked ? (
        <p className="request-quota__note">
          <Link to="/settings/media-accounts">{t("media:quota.link")}</Link>
        </p>
      ) : null}
    </>
  );
}

/**
 * #3: how many requests I have left — the request service's (Seerr) limits for films and series when my
 * account there is linked (they are the ones that count), else the portal's own allowance — plus the
 * requests bought in the shop, and where to buy more.
 */
export function QuotaSummary({ quota }: { quota?: RequestQuota | undefined }) {
  const t = useT();
  const fetched = useRequestQuota();
  const data = quota ?? fetched.data;
  if (!data) return null;
  return (
    <section className="request-quota" aria-label={t("media:quota.title")}>
      <header className="request-quota__head">
        <Icon name="coins" size={18} />
        <strong>{t("media:quota.title")}</strong>
      </header>
      <QuotaTiles quota={data} />
    </section>
  );
}

/** #3: one line before asking — what this request takes, or why it cannot be made now. */
export function QuotaLine({ kind }: { kind: "movie" | "series" }) {
  const t = useT();
  const format = useFormat();
  const quota = useRequestQuota().data;
  if (!quota) return null;
  const left = requestsLeft(quota, kind);
  const service = quota.service;
  const window =
    service && service.linked && "movie" in service ? (kind === "movie" ? service.movie : service.tv) : null;
  if (left === null) return <p className="request-quota__line">{t("media:quota.unlimitedLine")}</p>;
  if (left <= 0) {
    return (
      <p className="request-quota__line" data-restricted="true">
        <Icon name="warning" size={14} />
        {window?.renews_at
          ? t("media:quota.noneUntil", { date: format.date(window.renews_at, "medium") })
          : t("media:quota.none")}{" "}
        <Link to={SHOP}>{t("media:quota.buy")}</Link>
      </p>
    );
  }
  const paid = window ? window.restricted : quota.base_remaining <= 0;
  return (
    <p className="request-quota__line">
      {paid
        ? t("media:quota.usesBought", { count: quota.extra_units })
        : t("media:quota.leftLine", { count: left })}
    </p>
  );
}
