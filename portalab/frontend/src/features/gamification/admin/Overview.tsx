import { useId, useState } from "react";
import { Link } from "react-router";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AdminSection, AdminStats, AdminTabs, AdminToolbar } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useRules, useVerify, type Value } from "../api";
import { useLevelRewards, useProgress, useStreak, VALUES } from "./tuning";

const PERIODS = [7, 30, 90, 365];
// series colours come from the theme's tokens; the dash pattern keeps them apart without colour
const SERIES = [
  "var(--color-accent)",
  "var(--color-accent-alt)",
  "var(--cal-series)",
  "var(--cal-book)",
  "var(--cal-event)",
];
const DASHES = ["", "6 3", "2 3", "8 3 2 3", "1 4"];

function shortDay(day: string): string {
  return day.slice(5);
}

/**
 * Overview (027): how members progress — gains day by day, the running total of the members who progress
 * most, where gains come from — with the key figures of the economy (rules in force, streak, rewards).
 */
export function Overview({ onOpen }: { onOpen: (tab: string) => void }) {
  const t = useT();
  const format = useFormat();
  const tableId = useId();
  const [value, setValue] = useState<Value>("xp");
  const [days, setDays] = useState(30);
  const [table, setTable] = useState(false);
  const progress = useProgress(value, days);
  const rules = useRules();
  const streak = useStreak().query;
  const levels = useLevelRewards().query;
  const verify = useVerify();
  const data = progress.data;
  const total = (data?.days ?? []).reduce((sum, d) => sum + d.amount, 0);
  const active = (rules.data ?? []).filter((r) => r.status === "active").length;
  // one row per day, one column per leading member (their running total)
  const allDays = [...new Set((data?.members ?? []).flatMap((m) => m.points.map((p) => p.day)))].sort();
  const running = allDays.map((day) => {
    const row: Record<string, string | number> = { day: shortDay(day) };
    for (const member of data?.members ?? []) {
      const last = member.points.filter((p) => p.day <= day).at(-1);
      if (last) row[member.user_id] = last.total;
    }
    return row;
  });
  const daily = (data?.days ?? []).map((d) => ({
    day: shortDay(d.day),
    amount: d.amount,
    members: d.members,
  }));
  const unit = t(`gamification:value.${value}`);
  return (
    <>
      <AdminStats
        label={t("gamification:admin.overview.figures")}
        stats={[
          {
            key: "gained",
            icon: "trending",
            label: t("gamification:admin.overview.gained", { days }),
            value: `${format.number(total)} ${unit}`,
            tone: "info",
          },
          {
            key: "members",
            icon: "users",
            label: t("gamification:admin.overview.members"),
            value: format.number(Math.max(0, ...(data?.days ?? []).map((d) => d.members))),
            hint: t("gamification:admin.overview.membersHint"),
          },
          {
            key: "rules",
            icon: "zap",
            label: t("gamification:admin.overview.rules"),
            value: active,
            tone: active ? "ok" : "warn",
          },
          {
            key: "streak",
            icon: "flame",
            label: t("gamification:admin.tabs.streak"),
            value: streak.data?.enabled
              ? t("gamification:admin.streak.tierCount", { count: streak.data.tiers.length })
              : t("gamification:admin.off"),
            tone: streak.data?.enabled ? "ok" : "neutral",
          },
          {
            key: "levels",
            icon: "gift",
            label: t("gamification:admin.overview.levelRewards"),
            value: levels.data?.rewards.length ?? 0,
          },
        ]}
      />
      <AdminSection
        span="full"
        icon="chart"
        title={t("gamification:admin.overview.title")}
        description={t("gamification:admin.overview.hint")}
        actions={
          <Button
            variant="ghost"
            onClick={() => setTable(!table)}
            aria-expanded={table}
            aria-controls={tableId}
          >
            <Icon name="list" size={16} />
            {table ? t("gamification:admin.overview.hideTable") : t("gamification:admin.overview.showTable")}
          </Button>
        }
      >
        <AdminToolbar>
          <AdminTabs
            label={t("gamification:admin.grant.value")}
            current={value}
            onChange={(next) => setValue(next as Value)}
            tabs={VALUES.map((v) => ({ key: v, label: t(`gamification:value.${v}`) }))}
          />
          <AdminTabs
            label={t("gamification:admin.overview.period")}
            current={String(days)}
            onChange={(next) => setDays(Number(next))}
            tabs={PERIODS.map((p) => ({
              key: String(p),
              label: t("gamification:admin.overview.days", { days: p }),
            }))}
          />
        </AdminToolbar>
        {progress.isPending ? <FunctionalState state="loading" /> : null}
        {progress.isError ? <FunctionalState state="unavailable" onRetry={() => progress.refetch()} /> : null}
        {data && !data.days.length ? (
          <p className="admin-muted">{t("gamification:admin.overview.empty")}</p>
        ) : null}
        {data?.days.length ? (
          <div className="gam-charts">
            <figure className="gam-chart">
              <figcaption>{t("gamification:admin.overview.daily", { unit })}</figcaption>
              <div aria-hidden="true">
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={daily}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis dataKey="day" stroke="var(--color-text-muted)" fontSize={12} />
                    <YAxis stroke="var(--color-text-muted)" fontSize={12} width={48} />
                    <Tooltip />
                    <Bar dataKey="amount" name={unit} fill="var(--color-accent)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </figure>
            <figure className="gam-chart">
              <figcaption>{t("gamification:admin.overview.leaders", { unit })}</figcaption>
              <div aria-hidden="true">
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={running}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis dataKey="day" stroke="var(--color-text-muted)" fontSize={12} />
                    <YAxis stroke="var(--color-text-muted)" fontSize={12} width={56} />
                    <Tooltip />
                    <Legend />
                    {data.members.map((member, index) => (
                      <Line
                        key={member.user_id}
                        type="monotone"
                        dataKey={member.user_id}
                        name={member.name ?? member.user_id.slice(0, 8)}
                        stroke={SERIES[index % SERIES.length] ?? "var(--color-accent)"}
                        strokeDasharray={DASHES[index % DASHES.length] ?? ""}
                        strokeWidth={2}
                        dot={false}
                        connectNulls
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </figure>
          </div>
        ) : null}
        {data && table ? (
          <table id={tableId} className="admin-table" aria-label={t("gamification:admin.overview.title")}>
            <thead>
              <tr>
                <th scope="col">{t("gamification:admin.overview.day")}</th>
                <th scope="col" data-align="end">
                  {unit}
                </th>
                <th scope="col" data-align="end">
                  {t("gamification:admin.overview.members")}
                </th>
              </tr>
            </thead>
            <tbody>
              {data.days.map((d) => (
                <tr key={d.day}>
                  <td>{format.date(`${d.day}T12:00:00Z`, "medium")}</td>
                  <td data-align="end">{format.number(d.amount)}</td>
                  <td data-align="end">{format.number(d.members)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </AdminSection>
      <div className="admin-grid">
        <AdminSection icon="trophy" title={t("gamification:admin.overview.top")}>
          <ol className="gam-leaders">
            {(data?.members ?? []).map((member) => (
              <li key={member.user_id}>
                <span>{member.name ?? member.user_id.slice(0, 8)}</span>
                <strong>
                  +{format.number(member.gained)} {unit}
                </strong>
              </li>
            ))}
          </ol>
        </AdminSection>
        <AdminSection icon="zap" title={t("gamification:admin.overview.sources")}>
          <ul className="gam-sources">
            {(data?.sources ?? []).map((source) => (
              <li key={source.source}>
                <span>{source.source}</span>
                <span className="gam-sources__bar" aria-hidden="true">
                  <span style={{ inlineSize: `${total ? Math.round((source.amount / total) * 100) : 0}%` }} />
                </span>
                <strong>{format.number(source.amount)}</strong>
              </li>
            ))}
          </ul>
        </AdminSection>
        <AdminSection
          icon="shield"
          title={t("gamification:admin.verify")}
          description={t("gamification:admin.overview.verifyHint")}
        >
          <Button variant="secondary" onClick={() => verify.mutate()} disabled={verify.isPending}>
            <Icon name="check" size={16} />
            {t("gamification:admin.verify")}
          </Button>
          {verify.data ? (
            <p role="status">
              {verify.data.ok
                ? t("gamification:admin.verify.ok")
                : t("gamification:admin.verify.drift", { count: verify.data.drifts.length })}
            </p>
          ) : null}
          <p className="admin-muted">
            <Link to="/admin/statistics">{t("gamification:admin.overview.statistics")}</Link>
            {" · "}
            <Link to="/admin/campaigns">{t("gamification:admin.overview.campaigns")}</Link>
            {" · "}
            <button type="button" className="ds-link" onClick={() => onOpen("economy")}>
              {t("gamification:admin.tabs.economy")}
            </button>
          </p>
        </AdminSection>
      </div>
    </>
  );
}
