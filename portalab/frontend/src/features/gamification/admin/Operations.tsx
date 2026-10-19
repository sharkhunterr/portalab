import { useRef, useState } from "react";
import { AdminEmpty, AdminSection } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { SelectField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import type { Value } from "../api";
import { SOURCES } from "../progression/GainSources";
import { type Operation, useOperations, VALUES } from "./tuning";

const SIZES = [25, 50, 100];
const PLAYS = ["episode", "movie", "live", "book", "audiobook", "music", "game"];

/**
 * Issue 107 — the journal: every operation of every member over the period (or one member's, under the
 * overview's filter), the latest first — XP, Coins or Contribution gained, spent or corrected, what made it,
 * the balance right after and, for XP, the level reached. A real table on every screen (it scrolls sideways
 * on a phone, the date staying in view), page by page.
 */
export function Operations({
  days,
  member = "",
  memberName = null,
  onMember,
  mine = false,
}: {
  days: number;
  member?: string;
  memberName?: string | null;
  onMember?: (id: string) => void;
  /** issue 114: the member's own journal on their progression page (no member column) */
  mine?: boolean;
}) {
  const t = useT();
  const format = useFormat();
  const [value, setValue] = useState<Value | "">("");
  const [play, setPlay] = useState(""); // issue 160: one kind of play only
  const [size, setSize] = useState(SIZES[0] ?? 25);
  // where each page starts (the first at the top); a change of filter starts over
  const filters = `${days}|${member}|${value}|${size}|${play}`;
  const [pages, setPages] = useState<{ filters: string; cursors: (string | null)[] }>({
    filters,
    cursors: [null],
  });
  const cursors = pages.filters === filters ? pages.cursors : [null];
  const page = cursors.length - 1;
  const journal = useOperations(days, member, value, cursors[page] ?? null, size, mine, play);
  const rows = journal.data?.items ?? [];
  const total = journal.data?.total ?? 0;
  const next = journal.data?.next_cursor ?? null;
  const go = (to: (string | null)[]) => setPages({ filters, cursors: to });
  const title = mine
    ? t("gamification:history.title")
    : memberName
      ? t("gamification:admin.operations.oneTitle", { name: memberName })
      : t("gamification:admin.operations.title");
  const what = (row: Operation) =>
    row.source === "levels" && row.label
      ? t("gamification:admin.details.levelN", { level: row.label })
      : (row.label ?? t(`gamification:kind.${row.kind}`));
  const nameOf = (row: Operation) => row.name ?? row.user_id.slice(0, 8);
  // while the next page loads, the previous one stays — and so does its place in the count
  const settled = useRef(0);
  if (!journal.isPlaceholderData) settled.current = page;
  const shown = settled.current;
  const first = shown * size + 1;
  return (
    <AdminSection
      span="full"
      icon="clock"
      title={title}
      description={
        mine ? t("gamification:history.hint", { days }) : t("gamification:admin.operations.hint", { days })
      }
      actions={
        <span className="gam-ops__filters">
          <SelectField
            label={t("gamification:sources.value")}
            value={value}
            onChange={(event) => setValue(event.target.value as Value | "")}
          >
            <option value="">{t("gamification:admin.operations.allValues")}</option>
            {VALUES.map((v) => (
              <option key={v} value={v}>
                {t(`gamification:value.${v}`)}
              </option>
            ))}
          </SelectField>
          <SelectField
            label={t("gamification:plays.filter")}
            value={play}
            onChange={(event) => setPlay(event.target.value)}
          >
            <option value="">{t("gamification:plays.allKinds")}</option>
            {PLAYS.map((kind) => (
              <option key={kind} value={kind}>
                {t(`gamification:sources.${kind}`)}
              </option>
            ))}
          </SelectField>
        </span>
      }
      flush
    >
      {journal.isPending ? <FunctionalState state="loading" /> : null}
      {journal.isError ? <FunctionalState state="unavailable" onRetry={() => journal.refetch()} /> : null}
      {journal.data && rows.length === 0 ? (
        <AdminEmpty icon="clock" title={t("gamification:admin.overview.empty")} />
      ) : null}
      {rows.length ? (
        <>
          {/* biome-ignore lint/a11y/noNoninteractiveTabindex: a scrolling region must be reachable by keyboard */}
          <section className="gam-ops__scroll" tabIndex={0} aria-label={title}>
            <table className="gam-ops" aria-label={title} aria-busy={journal.isFetching || undefined}>
              <thead>
                <tr>
                  <th scope="col">{t("gamification:admin.operations.when")}</th>
                  {mine ? null : <th scope="col">{t("gamification:admin.overview.member")}</th>}
                  <th scope="col" data-align="end">
                    {t("gamification:admin.operations.amount")}
                  </th>
                  <th scope="col">{t("gamification:admin.operations.source")}</th>
                  <th scope="col">{t("gamification:admin.operations.what")}</th>
                  <th scope="col" data-align="end">
                    {t("gamification:admin.operations.balance")}
                  </th>
                  <th scope="col">{t("gamification:admin.details.level")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <th scope="row" className="gam-ops__when">
                      <span>{format.date(row.occurred_at, "short")}</span>
                      <span className="admin-muted">{format.time(row.occurred_at)}</span>
                    </th>
                    {mine ? null : (
                      <td>
                        {member || !onMember ? (
                          nameOf(row)
                        ) : (
                          <button type="button" className="ds-link" onClick={() => onMember(row.user_id)}>
                            {nameOf(row)}
                          </button>
                        )}
                      </td>
                    )}
                    <td data-align="end">
                      <span className="gam-ops__amount" data-sign={row.delta < 0 ? "minus" : "plus"}>
                        {row.delta > 0 ? "+" : ""}
                        {format.number(row.delta)} {t(`gamification:value.${row.value}`)}
                      </span>
                    </td>
                    <td>
                      <span className="gam-ops__source">
                        <span
                          className="gam-ops__dot"
                          style={{ background: SOURCES[row.source]?.color ?? "var(--cal-other)" }}
                          aria-hidden="true"
                        >
                          <Icon name={SOURCES[row.source]?.icon ?? "sparkles"} size={12} />
                        </span>
                        {t(`gamification:sources.${row.source}`)}
                      </span>
                    </td>
                    <td className="gam-ops__what">
                      {row.title ? <strong>{row.title}</strong> : null}
                      {row.title ? <span className="admin-muted">{what(row)}</span> : what(row)}
                      {row.reason ? <span className="admin-muted">{row.reason}</span> : null}
                    </td>
                    <td data-align="end" className="gam-ops__num">
                      {format.number(row.balance)}
                    </td>
                    <td>
                      {row.level == null ? (
                        "—"
                      ) : row.level_up ? (
                        <strong className="gam-ops__up">
                          <Icon name="trending" size={14} />
                          {t("gamification:admin.operations.levelUp", { level: row.level })}
                        </strong>
                      ) : (
                        String(row.level)
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <nav className="gam-ops__pager" aria-label={t("gamification:admin.operations.pages")}>
            <span className="admin-muted" aria-live="polite">
              {t("gamification:admin.operations.range", {
                first: format.number(first),
                last: format.number(first + rows.length - 1),
                count: total,
              })}
            </span>
            <SelectField
              label={t("gamification:admin.operations.size")}
              value={String(size)}
              onChange={(event) => setSize(Number(event.target.value))}
            >
              {SIZES.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </SelectField>
            <span className="gam-ops__buttons">
              <Button
                variant="secondary"
                disabled={page === 0 || journal.isFetching}
                onClick={() => go(cursors.slice(0, -1))}
              >
                <Icon name="chevron-left" size={16} />
                {t("gamification:admin.operations.previous")}
              </Button>
              <span className="gam-ops__page">
                {t("gamification:admin.operations.page", {
                  page: shown + 1,
                  pages: Math.max(1, Math.ceil(total / size)),
                })}
              </span>
              <Button
                variant="secondary"
                disabled={!next || journal.isFetching}
                onClick={() => go([...cursors, next])}
              >
                {t("gamification:admin.operations.next")}
                <Icon name="chevron-right" size={16} />
              </Button>
            </span>
          </nav>
        </>
      ) : null}
    </AdminSection>
  );
}
