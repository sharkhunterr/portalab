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
import { SelectField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useRules, useVerify, type Value } from "../api";
import { SOURCES } from "../progression/GainSources";
import { AnomalyQueue } from "./AnomalyQueue";
import { MemberDetails } from "./MemberDetails";
import { Operations } from "./Operations";
import { useLevelRewards, useMembersProgress, useProgress, useStreak, VALUES } from "./tuning";

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

/** Axis ticks: 1.2k, 500k, 3M — never cut. */
const compact = (value: number) =>
  new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(value);

/**
 * Overview (027): how members progress — with the key figures of the economy (rules in force, streak,
 * rewards). Issue 104: for every member or one of them (a filter over all the charts): what made them gain day
 * by day, stacked by kind as on a member's own progression page; each one's running balance; and every
 * member side by side, their gains stacked by kind.
 */
export function Overview() {
  const t = useT();
  const format = useFormat();
  const tableId = useId();
  const [value, setValue] = useState<Value>("xp");
  const [days, setDays] = useState(30);
  const [member, setMember] = useState(""); // issue 104: every member, or one of them
  const [table, setTable] = useState(false);
  const progress = useProgress(value, days);
  const everyone = useMembersProgress(value, days);
  const rules = useRules();
  const streak = useStreak().query;
  const levels = useLevelRewards().query;
  const verify = useVerify();
  const data = progress.data;
  const all = everyone.data?.members ?? [];
  const shown = member ? all.filter((m) => m.user_id === member) : all;
  const nameOf = (m: { name?: string | null; user_id: string }) => m.name ?? m.user_id.slice(0, 8);
  const label = (source: string) => t(`gamification:sources.${source}`);
  // what made them gain, by kind (the members' own « where my XP comes from »), in all and day by day
  const bySource = new Map<string, number>();
  const byDay = new Map<string, Record<string, number>>();
  for (const m of shown) {
    for (const s of m.sources) bySource.set(s.source, (bySource.get(s.source) ?? 0) + s.amount);
    for (const d of m.days) {
      const row = byDay.get(d.day) ?? {};
      for (const [source, amount] of Object.entries(d.amounts)) row[source] = (row[source] ?? 0) + amount;
      byDay.set(d.day, row);
    }
  }
  const sources = [...bySource.entries()]
    .filter(([, amount]) => amount > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([source, amount]) => ({ source, amount }));
  const keys = sources.map((s) => s.source);
  const total = sources.reduce((sum, s) => sum + s.amount, 0);
  const days_ = [...byDay.keys()].sort();
  const daily = days_.map((day) => ({ day: shortDay(day), ...byDay.get(day) }));
  // one row per day, one column per member shown (their running balance)
  const allDays = [...new Set(shown.flatMap((m) => m.points.map((p) => p.day)))].sort();
  const running = allDays.map((day) => {
    const row: Record<string, string | number> = { day: shortDay(day) };
    for (const m of shown) {
      const last = m.points.filter((p) => p.day <= day).at(-1);
      if (last) row[m.user_id] = last.total;
    }
    return row;
  });
  // every member side by side, their gains stacked by kind
  const perMember = all
    .filter((m) => m.gained > 0)
    .map((m) => ({
      name: nameOf(m),
      ...Object.fromEntries(m.sources.map((s) => [s.source, s.amount])),
    }));
  const memberKeys = [...new Set(all.flatMap((m) => m.sources.map((s) => s.source)))];
  const active = (rules.data ?? []).filter((r) => r.status === "active").length;
  const unit = t(`gamification:value.${value}`);
  const tooltip = {
    contentStyle: { background: "var(--color-surface-raised)", border: "1px solid var(--color-border)" },
  };
  const leaders = [...shown].sort((a, b) => b.gained - a.gained).slice(0, 10);
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
          <SelectField
            label={t("gamification:admin.overview.member")}
            value={member}
            onChange={(e) => setMember(e.target.value)}
          >
            <option value="">{t("gamification:admin.overview.everyone", { count: all.length })}</option>
            {all.map((m) => (
              <option key={m.user_id} value={m.user_id}>
                {nameOf(m)}
              </option>
            ))}
          </SelectField>
        </AdminToolbar>
        {everyone.isPending ? <FunctionalState state="loading" /> : null}
        {everyone.isError ? <FunctionalState state="unavailable" onRetry={() => everyone.refetch()} /> : null}
        {everyone.data && !daily.length ? (
          <p className="admin-muted">{t("gamification:admin.overview.empty")}</p>
        ) : null}
        {daily.length ? (
          <div className="gam-charts">
            <figure className="gam-chart">
              <figcaption>{t("gamification:admin.overview.daily", { unit })}</figcaption>
              <div aria-hidden="true">
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={daily}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                    <XAxis dataKey="day" stroke="var(--color-text-muted)" fontSize={12} />
                    <YAxis
                      stroke="var(--color-text-muted)"
                      fontSize={12}
                      width={48}
                      tickFormatter={compact}
                    />
                    <Tooltip {...tooltip} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    {keys.map((key, index) => (
                      <Bar
                        key={key}
                        dataKey={key}
                        name={label(key)}
                        stackId="gains"
                        fill={SOURCES[key]?.color ?? "var(--cal-other)"}
                        radius={index === keys.length - 1 ? [4, 4, 0, 0] : 0}
                        isAnimationActive={false}
                      />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </figure>
            <figure className="gam-chart">
              <figcaption>
                {member
                  ? t("gamification:admin.overview.runningOne", {
                      unit,
                      name: nameOf(shown[0] ?? { user_id: member }),
                    })
                  : t("gamification:admin.overview.runningAll", { unit })}
              </figcaption>
              <div aria-hidden="true">
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={running}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis dataKey="day" stroke="var(--color-text-muted)" fontSize={12} />
                    <YAxis
                      stroke="var(--color-text-muted)"
                      fontSize={12}
                      width={56}
                      tickFormatter={compact}
                    />
                    <Tooltip {...tooltip} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    {shown.map((m) => {
                      const index = all.indexOf(m);
                      return (
                        <Line
                          key={m.user_id}
                          type="monotone"
                          dataKey={m.user_id}
                          name={nameOf(m)}
                          stroke={SERIES[index % SERIES.length] ?? "var(--color-accent)"}
                          strokeDasharray={DASHES[Math.floor(index / SERIES.length) % DASHES.length] ?? ""}
                          strokeWidth={2}
                          dot={false}
                          connectNulls
                          isAnimationActive={false}
                        />
                      );
                    })}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </figure>
            {!member && perMember.length ? (
              <figure className="gam-chart gam-chart--wide">
                <figcaption>{t("gamification:admin.overview.perMember", { unit })}</figcaption>
                <div aria-hidden="true">
                  <ResponsiveContainer width="100%" height={Math.max(160, perMember.length * 36 + 60)}>
                    <BarChart data={perMember} layout="vertical" margin={{ left: 8, right: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
                      <XAxis
                        type="number"
                        stroke="var(--color-text-muted)"
                        fontSize={12}
                        tickFormatter={compact}
                      />
                      <YAxis
                        type="category"
                        dataKey="name"
                        stroke="var(--color-text-muted)"
                        fontSize={12}
                        width={110}
                      />
                      <Tooltip {...tooltip} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      {memberKeys.map((key) => (
                        <Bar
                          key={key}
                          dataKey={key}
                          name={label(key)}
                          stackId="member"
                          fill={SOURCES[key]?.color ?? "var(--cal-other)"}
                          isAnimationActive={false}
                        />
                      ))}
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </figure>
            ) : null}
          </div>
        ) : null}
        {everyone.data && table ? (
          <table id={tableId} className="admin-table" aria-label={t("gamification:admin.overview.title")}>
            <thead>
              <tr>
                <th scope="col">{t("gamification:admin.overview.day")}</th>
                {keys.map((key) => (
                  <th key={key} scope="col" data-align="end">
                    {label(key)}
                  </th>
                ))}
                <th scope="col" data-align="end">
                  {unit}
                </th>
              </tr>
            </thead>
            <tbody>
              {days_.map((day) => {
                const row = byDay.get(day) ?? {};
                return (
                  <tr key={day}>
                    <td>{format.date(`${day}T12:00:00Z`, "medium")}</td>
                    {keys.map((key) => (
                      <td key={key} data-align="end">
                        {format.number(row[key] ?? 0)}
                      </td>
                    ))}
                    <td data-align="end">
                      {format.number(Object.values(row).reduce((sum, n) => sum + n, 0))}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : null}
      </AdminSection>
      <Operations
        days={days}
        member={member}
        memberName={member ? nameOf(all.find((m) => m.user_id === member) ?? { user_id: member }) : null}
        onMember={setMember}
      />
      <MemberDetails days={days} member={member} onMember={setMember} />
      <div className="admin-grid">
        <AdminSection icon="trophy" title={t("gamification:admin.overview.top")}>
          <ol className="gam-leaders">
            {leaders.map((m) => (
              <li key={m.user_id}>
                <button type="button" className="ds-link" onClick={() => setMember(m.user_id)}>
                  {nameOf(m)}
                </button>
                <strong>
                  +{format.number(m.gained)} {unit}
                </strong>
              </li>
            ))}
          </ol>
        </AdminSection>
        <AdminSection icon="zap" title={t("gamification:admin.overview.sources")}>
          <ul className="gam-sources">
            {sources.map((source) => (
              <li key={source.source}>
                <span className="gam-sources__name">
                  <Icon name={SOURCES[source.source]?.icon ?? "sparkles"} size={14} />
                  <span>{label(source.source)}</span>
                </span>
                <span className="gam-sources__bar" aria-hidden="true">
                  <span
                    style={{
                      inlineSize: `${total ? Math.round((source.amount / total) * 100) : 0}%`,
                      background: SOURCES[source.source]?.color ?? "var(--cal-other)",
                    }}
                  />
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
            <Link to="/admin/marketplace/members">{t("gamification:admin.overview.balances")}</Link>
          </p>
        </AdminSection>
        <AnomalyQueue />
      </div>
    </>
  );
}
