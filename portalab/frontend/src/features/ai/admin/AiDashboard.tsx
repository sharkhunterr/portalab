import { useState } from "react";
import { Link } from "react-router";
import {
  AdminEmpty,
  AdminGrid,
  AdminSection,
  AdminStats,
  AdminTable,
  StatusBadge,
} from "../../../design-system/admin/AdminKit";
import { BarsChart } from "../../../design-system/charts/Charts";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { maybe } from "../../automations/labels";
import { useAiDashboard } from "../api";

const PERIODS = [7, 30, 90] as const;

/** The hours, the viewer's own: the server counts them in UTC. */
function localHours(hoursUtc: number[]): number[] {
  const shift = Math.round(-new Date().getTimezoneOffset() / 60);
  return Array.from({ length: 24 }, (_, hour) => hoursUtc[(((hour - shift) % 24) + 24) % 24] ?? 0);
}

/**
 * Issue 176 — the assistant at a glance: how many questions, from how many members, how many answered
 * (with the portal's data or not), the errors, how long an answer takes, what the members thought of the
 * answers; day by day, hour by hour; who asks most, which tools it used (and failed), which models
 * answered — and the answers rated « not as expected », with their question, to improve its instructions.
 */
export function AiDashboard() {
  const t = useT();
  const format = useFormat();
  const [days, setDays] = useState<number>(30);
  const board = useAiDashboard(days);
  if (board.isPending) return <FunctionalState state="loading" />;
  if (board.isError || !board.data)
    return <FunctionalState state="unavailable" onRetry={() => board.refetch()} />;
  const data = board.data;
  const { totals } = data;
  const share = (part: number, whole: number) => (whole ? format.percent(part / whole) : "—");
  const seconds = (ms: number | null) =>
    ms === null ? "—" : t("ai:board.seconds", { s: format.number(Math.round(ms / 100) / 10) });
  const rated = totals.rated_up + totals.rated_down;
  const series = data.per_day.map((day) => ({
    day: format.date(`${day.day}T12:00:00Z`, "short"),
    questions: day.questions - day.errors > 0 ? day.questions - day.errors : 0,
    errors: day.errors,
    members: day.members,
  }));
  const hours = localHours(data.hours_utc);
  const peak = Math.max(1, ...hours);
  const toolLabel = (name: string) => maybe(t, `ai:tool.${name}.label`, name);
  return (
    <div className="ds-stack">
      <fieldset className="ds-subnav ai-board__period">
        <legend className="visually-hidden">{t("ai:board.period")}</legend>
        {PERIODS.map((value) => (
          <button key={value} type="button" aria-pressed={days === value} onClick={() => setDays(value)}>
            {t("ai:board.days", { count: value })}
          </button>
        ))}
      </fieldset>
      <AdminStats
        label={t("ai:board.figures")}
        stats={[
          {
            key: "questions",
            icon: "message",
            label: t("ai:board.questions"),
            value: format.number(totals.questions),
            hint: t("ai:board.members", { count: totals.members }),
          },
          {
            key: "answered",
            icon: "check",
            tone: totals.errors ? "warn" : "ok",
            label: t("ai:board.answered"),
            value: share(totals.answered, totals.questions),
            hint: t("ai:board.errors", { count: totals.errors + totals.unanswered }),
          },
          {
            key: "sourced",
            icon: "database",
            label: t("ai:board.sourced"),
            value: share(totals.sourced, totals.answered),
            hint: t("ai:board.nudged", { count: totals.nudged }),
          },
          {
            key: "latency",
            icon: "clock",
            label: t("ai:board.latency"),
            value: seconds(totals.latency_median_ms),
            hint: t("ai:board.latencyP90", { s: seconds(totals.latency_p90_ms) }),
          },
          {
            key: "verdicts",
            icon: "thumbs-up",
            tone: rated && totals.rated_down > totals.rated_up ? "bad" : rated ? "ok" : "neutral",
            label: t("ai:board.verdicts"),
            value: rated ? share(totals.rated_up, rated) : "—",
            hint: t("ai:board.verdictsHint", { up: totals.rated_up, down: totals.rated_down }),
          },
          {
            key: "tokens",
            icon: "activity",
            label: t("ai:board.perAnswer"),
            value: totals.tokens_per_answer === null ? "—" : format.compact(totals.tokens_per_answer),
          },
        ]}
      />
      <AdminGrid>
        <AdminSection title={t("ai:board.perDay")} icon="chart" span="full">
          {series.length ? (
            <div className="ai-board__chart">
              <BarsChart
                data={series}
                x="day"
                stacked
                height={220}
                format={(value) => format.number(value)}
                series={[
                  { key: "questions", label: t("ai:board.chart.answered"), color: "var(--color-accent)" },
                  { key: "errors", label: t("ai:board.chart.errors"), color: "var(--state-error-fg)" },
                ]}
              />
            </div>
          ) : (
            <AdminEmpty icon="message" title={t("ai:board.none")} />
          )}
        </AdminSection>
        <AdminSection title={t("ai:board.hours")} icon="clock" description={t("ai:board.hoursHint")}>
          <ol className="ai-board__hours" aria-label={t("ai:board.hours")}>
            {hours.map((count, hour) => (
              <li
                // biome-ignore lint/suspicious/noArrayIndexKey: the 24 hours of a day
                key={hour}
                className="ai-board__hour"
                data-empty={count ? undefined : true}
                title={t("ai:board.hourCount", { hour, count })}
              >
                <span
                  className="ai-board__hour-bar"
                  style={{ blockSize: `${Math.round((count / peak) * 100)}%` }}
                />
                <span aria-hidden="true">{hour % 6 === 0 ? hour : ""}</span>
                <span className="visually-hidden">{t("ai:board.hourCount", { hour, count })}</span>
              </li>
            ))}
          </ol>
        </AdminSection>
        <AdminSection title={t("ai:board.who")} icon="users" flush>
          <AdminTable
            label={t("ai:board.who")}
            rows={data.members}
            rowKey={(row) => row.user_id}
            empty={<AdminEmpty icon="users" title={t("ai:board.none")} />}
            columns={[
              {
                key: "name",
                header: t("ai:board.member"),
                primary: true,
                render: (row) => (
                  <Link to={`/community/members/${row.user_id}`}>{row.name ?? t("ai:board.someone")}</Link>
                ),
              },
              {
                key: "questions",
                header: t("ai:board.questions"),
                align: "end",
                render: (row) => format.number(row.questions),
              },
              { key: "last", header: t("ai:board.last"), render: (row) => format.dateTime(row.last_at) },
            ]}
          />
        </AdminSection>
        <AdminSection title={t("ai:board.tools")} icon="wrench" flush>
          <AdminTable
            label={t("ai:board.tools")}
            rows={data.tools}
            rowKey={(row) => row.name}
            empty={<AdminEmpty icon="wrench" title={t("ai:board.noTools")} />}
            columns={[
              {
                key: "name",
                header: t("ai:board.tool"),
                primary: true,
                render: (row) => toolLabel(row.name),
              },
              {
                key: "calls",
                header: t("ai:board.calls"),
                align: "end",
                render: (row) => format.number(row.calls),
              },
              {
                key: "failed",
                header: t("ai:board.failed"),
                align: "end",
                render: (row) =>
                  row.failed ? (
                    <StatusBadge tone="warn">{format.number(row.failed)}</StatusBadge>
                  ) : (
                    format.number(0)
                  ),
              },
            ]}
          />
        </AdminSection>
        <AdminSection title={t("ai:board.models")} icon="brain" flush>
          <AdminTable
            label={t("ai:board.models")}
            rows={[
              ...data.models.map((m) => ({
                key: `m:${m.model}`,
                label: m.model,
                count: m.answers,
                bad: false,
              })),
              ...data.errors.map((e) => ({
                key: `e:${e.code}`,
                label: maybe(t, `ai:board.error.${e.code}`, e.code),
                count: e.count,
                bad: true,
              })),
            ]}
            rowKey={(row) => row.key}
            empty={<AdminEmpty icon="brain" title={t("ai:board.none")} />}
            columns={[
              {
                key: "label",
                header: t("ai:board.modelOrError"),
                primary: true,
                render: (row) => (row.bad ? <StatusBadge tone="bad">{row.label}</StatusBadge> : row.label),
              },
              {
                key: "count",
                header: t("ai:board.answers"),
                align: "end",
                render: (row) => format.number(row.count),
              },
            ]}
          />
        </AdminSection>
        <AdminSection
          title={t("ai:board.ratedDown")}
          icon="thumbs-down"
          span="full"
          description={t("ai:board.ratedDownHint")}
        >
          {data.rated_down.length ? (
            <ol className="ai-board__rated">
              {data.rated_down.map((item) => (
                <li key={item.message_id} className="ai-board__case">
                  <header>
                    <span>{item.member ?? t("ai:board.someone")}</span>
                    <span>{format.dateTime(item.at)}</span>
                    {item.tools.length ? <span>{item.tools.map(toolLabel).join(" · ")}</span> : null}
                    {item.error ? <StatusBadge tone="bad">{item.error}</StatusBadge> : null}
                  </header>
                  <p className="ai-board__question">{item.question || "—"}</p>
                  <p className="ai-board__answer">{item.answer}</p>
                  {item.comment ? <p className="ai-board__comment">{item.comment}</p> : null}
                </li>
              ))}
            </ol>
          ) : (
            <AdminEmpty icon="thumbs-up" title={t("ai:board.noRatedDown")} />
          )}
        </AdminSection>
      </AdminGrid>
    </div>
  );
}
