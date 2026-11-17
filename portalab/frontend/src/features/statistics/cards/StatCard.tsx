import type { ReactNode } from "react";
import { AdminSection } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { type CatalogEntry, type StatQuery, useStatistic } from "../api";
import { StatChart } from "../charts/StatChart";
import { statIcon, TrendBadge } from "./look";

type Props = { entry: CatalogEntry; query: Omit<StatQuery, "key">; onHide?: (() => void) | undefined };

function HideButton({ entry, onHide }: Pick<Props, "entry" | "onHide">) {
  const t = useT();
  if (!entry.hideable || !onHide) return null;
  return (
    <Button
      variant="ghost"
      size="icon"
      className="stat-hide"
      aria-label={t("statistics:hideOne", { title: t(entry.title_key) })}
      title={t("statistics:hide")}
      onClick={onHide}
    >
      <Icon name="hide" size={16} />
    </Button>
  );
}

/**
 * One statistic as a section of the page (spec 017 T016; issue 481: My media's look — a titled section with
 * its icon and description, the figure and its trend badge, the chart): its own query and functional state —
 * locked (hint only), insufficient data, stale/partial with ``as_of``, unavailable. Hiding is offered only for
 * hideable statistics.
 */
export function StatCard({ entry, query, onHide }: Props) {
  const t = useT();
  const title = t(entry.title_key);
  const stat = useStatistic({ ...query, key: entry.key }, !entry.locked);
  const result = stat.data;
  let body: ReactNode;
  if (entry.locked || result?.state === "locked") {
    const hint = entry.unlock_hint ?? result?.unlock_hint;
    body = (
      <FunctionalState
        state="unauthorized"
        label={t("statistics:locked")}
        detail={hint ? t(hint) : undefined}
      />
    );
  } else if (stat.isPending) {
    body = <FunctionalState state="loading" />;
  } else if (stat.isError || !result) {
    body = <FunctionalState state="error" onRetry={() => stat.refetch()} />;
  } else if (result.state === "insufficient_data") {
    body = <FunctionalState state="no-data" label={t("statistics:insufficient")} />;
  } else if (result.state === "unavailable") {
    body = <FunctionalState state="unavailable" onRetry={() => stat.refetch()} />;
  } else if (result.state === "no_data") {
    body = <FunctionalState state="no-data" label={t("statistics:nothing")} />;
  } else {
    body = (
      <>
        {result.state === "partial" || result.state === "stale" ? (
          <FunctionalState state={result.state} asOf={result.as_of ? new Date(result.as_of) : undefined} />
        ) : null}
        <StatChart result={result} viz={entry.viz} title={title} />
      </>
    );
  }
  return (
    <div className="stat-card" data-statistic={entry.key}>
      <AdminSection
        title={title}
        icon={statIcon(entry.key, entry.domain)}
        description={entry.description_key ? t(entry.description_key) : undefined}
        actions={<HideButton entry={entry} onHide={onHide} />}
      >
        {body}
      </AdminSection>
    </div>
  );
}

/**
 * Issue 481: a single figure as a tile of the page's head row (My media's tiles): its icon and name, the
 * figure, its trend badge — or why there is none (locked, too few members, nothing yet).
 */
export function StatTile({ entry, query, onHide }: Props) {
  const t = useT();
  const format = useFormat();
  const title = t(entry.title_key);
  const stat = useStatistic({ ...query, key: entry.key }, !entry.locked);
  const result = stat.data;
  const locked = entry.locked || result?.state === "locked";
  const value =
    locked || stat.isError || !result || result.value === null
      ? stat.isPending && !locked
        ? "…"
        : "—"
      : format.number(result.value);
  const hint = locked ? (
    <span className="stat-trend" data-trend="none">
      <Icon name="lock" size={14} />
      {t("statistics:locked")}
    </span>
  ) : result?.state === "insufficient_data" ? (
    <span className="stat-trend" data-trend="none" title={t("statistics:insufficient")}>
      {t("statistics:badge.insufficient")}
    </span>
  ) : result?.state === "no_data" ? (
    <span className="stat-trend" data-trend="none">
      {t("statistics:nothing")}
    </span>
  ) : result ? (
    <TrendBadge result={result} />
  ) : null;
  const tone =
    result?.trend?.direction === "up" ? "ok" : result?.trend?.direction === "down" ? "warn" : "info";
  return (
    <li
      className="admin-stat stat-tile"
      data-tone={locked || !result?.trend ? "neutral" : tone}
      data-statistic={entry.key}
      title={entry.description_key ? t(entry.description_key) : undefined}
    >
      <span className="admin-stat__label">
        <Icon name={statIcon(entry.key, entry.domain)} size={16} />
        {title}
      </span>
      <span className="admin-stat__value">{value}</span>
      {hint ? <span className="admin-stat__hint">{hint}</span> : null}
      <HideButton entry={entry} onHide={onHide} />
    </li>
  );
}
