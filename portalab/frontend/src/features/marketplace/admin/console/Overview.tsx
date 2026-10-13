import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  AdminEmpty,
  AdminGrid,
  AdminSection,
  AdminTable,
  StatusBadge,
} from "../../../../design-system/admin/AdminKit";
import { FunctionalState } from "../../../../design-system/state/FunctionalState";
import { useFormat } from "../../../../i18n/format/useFormat";
import { useT } from "../../../../i18n/hooks/useT";
import { type Activity, useEconomy, useMemberName, useNameOf, useOverview } from "./api";
import { Kpis } from "./Kpis";

const PERIODS = [7, 30, 90] as const;
const TONES: Record<Activity["kind"], "ok" | "warn" | "bad" | "neutral"> = {
  purchase: "ok",
  grant: "neutral",
  booster: "ok",
  booster_item: "neutral",
  revoked: "bad",
  refunded: "warn",
  request: "warn",
};

/**
 * #98 — what is going on in the shop: purchases and Coins spent, grants, boosters opened, refunds and
 * requests waiting over a period; Coins in circulation and earned against spent day by day; the best
 * sellers and the latest activity, each member opening their console.
 */
export function Overview({ onMember }: { onMember: (id: string) => void }) {
  const t = useT();
  const format = useFormat();
  const nameOf = useNameOf();
  const memberName = useMemberName();
  const [days, setDays] = useState<number>(30);
  const overview = useOverview(days);
  const economy = useEconomy(days);
  if (overview.isPending) return <FunctionalState state="loading" />;
  if (overview.isError || !overview.data)
    return <FunctionalState state="unavailable" onRetry={() => overview.refetch()} />;
  const data = overview.data;
  const coins = (n: number) => t("marketplace:shopadmin.coins", { count: n });
  const series = data.series.map((day, index) => ({
    day: format.date(`${day.day}T12:00:00Z`, "short"),
    purchases: day.purchases,
    boosters: day.boosters,
    grants: day.grants,
    spent: economy.data?.series[index]?.coins_spent ?? day.coins,
    earned: economy.data?.series[index]?.coins_earned ?? 0,
  }));
  const tooltip = {
    contentStyle: { background: "var(--color-surface-raised)", border: "1px solid var(--color-border)" },
  };
  return (
    <div className="mk-console">
      <fieldset className="ds-subnav mk-console__period">
        <legend className="visually-hidden">{t("marketplace:shopadmin.period")}</legend>
        {PERIODS.map((value) => (
          <button key={value} type="button" aria-pressed={days === value} onClick={() => setDays(value)}>
            {t("marketplace:shopadmin.days", { count: value })}
          </button>
        ))}
      </fieldset>
      <Kpis
        label={t("marketplace:shopadmin.overview")}
        items={[
          {
            key: "purchases",
            icon: "shop",
            label: t("marketplace:shopadmin.stat.purchases"),
            value: format.number(data.purchases + data.boosters_opened),
            hint: t("marketplace:shopadmin.stat.buyersCoins", {
              count: data.buyers,
              coins: data.coins_spent,
            }),
          },
          {
            key: "circulation",
            icon: "wallet",
            tone: "ok",
            label: t("marketplace:shopadmin.stat.circulation"),
            value: economy.data ? format.number(economy.data.coins_in_circulation) : "…",
            hint: economy.data
              ? t("marketplace:shopadmin.stat.flow", {
                  earned: economy.data.coins_earned,
                  spent: economy.data.coins_spent,
                })
              : undefined,
          },
          {
            key: "requests",
            icon: "inbox",
            tone: data.requests_pending ? "warn" : "muted",
            label: t("marketplace:shopadmin.stat.requests"),
            value: format.number(data.requests_pending),
            hint: data.requests_pending ? t("marketplace:shopadmin.stat.toHandle") : undefined,
            to: "/admin/marketplace/requests",
          },
          {
            key: "boosters",
            icon: "gift",
            label: t("marketplace:shopadmin.stat.boosters"),
            value: format.number(data.boosters_opened),
            hint: data.booster_coins
              ? t("marketplace:shopadmin.coins", { count: data.booster_coins })
              : undefined,
          },
          {
            key: "grants",
            icon: "star",
            tone: "muted",
            label: t("marketplace:shopadmin.stat.grants"),
            value: format.number(data.grants),
            hint: data.refunds
              ? t("marketplace:shopadmin.stat.refundsCount", { count: data.refunds })
              : undefined,
          },
          {
            key: "catalog",
            icon: "list",
            tone: "muted",
            label: t("marketplace:shopadmin.stat.onSale"),
            value: format.number(data.products_on_sale),
            hint: t("marketplace:shopadmin.stat.owned", { count: data.items_owned }),
            to: "/admin/marketplace/catalog",
          },
        ]}
      />
      <AdminGrid>
        <AdminSection title={t("marketplace:shopadmin.chart.activity")} icon="chart" span="full">
          <div className="mk-console__chart">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={series} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} interval="preserveStartEnd" minTickGap={18} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip {...tooltip} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar
                  dataKey="purchases"
                  name={t("marketplace:shopadmin.chart.purchases")}
                  stackId="a"
                  fill="var(--color-accent)"
                  isAnimationActive={false}
                />
                <Bar
                  dataKey="boosters"
                  name={t("marketplace:shopadmin.chart.boosters")}
                  stackId="a"
                  fill="var(--color-accent-alt)"
                  isAnimationActive={false}
                />
                <Bar
                  dataKey="grants"
                  name={t("marketplace:shopadmin.chart.grants")}
                  stackId="a"
                  fill="var(--color-text-muted)"
                  isAnimationActive={false}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </AdminSection>
        <AdminSection title={t("marketplace:shopadmin.chart.coins")} icon="coins" span="full">
          <div className="mk-console__chart">
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={series} margin={{ top: 8, right: 8, bottom: 0, left: -6 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} interval="preserveStartEnd" minTickGap={18} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip {...tooltip} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar
                  dataKey="earned"
                  name={t("marketplace:shopadmin.chart.earned")}
                  fill="var(--color-accent)"
                  isAnimationActive={false}
                />
                <Bar
                  dataKey="spent"
                  name={t("marketplace:shopadmin.chart.spent")}
                  fill="var(--color-accent-alt)"
                  isAnimationActive={false}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </AdminSection>
        <AdminSection title={t("marketplace:shopadmin.top")} icon="trending" flush>
          <AdminTable
            label={t("marketplace:shopadmin.top")}
            rows={data.top}
            rowKey={(row) => row.key}
            empty={<AdminEmpty icon="shop" title={t("marketplace:shopadmin.none")} />}
            columns={[
              {
                key: "name",
                header: t("marketplace:shopadmin.col.product"),
                primary: true,
                render: (row) => (
                  <span className="mk-console__product">
                    <strong>{nameOf(row.names, row.key)}</strong>
                    <small>{t(`marketplace:type.${row.type}`)}</small>
                  </span>
                ),
              },
              {
                key: "count",
                header: t("marketplace:shopadmin.col.sold"),
                align: "end",
                render: (row) => row.count,
              },
              {
                key: "coins",
                header: t("marketplace:shopadmin.col.coins"),
                align: "end",
                render: (row) => coins(row.coins),
              },
            ]}
          />
        </AdminSection>
        <AdminSection title={t("marketplace:shopadmin.richest")} icon="wallet" flush>
          <AdminTable
            label={t("marketplace:shopadmin.richest")}
            rows={(economy.data?.holders ?? []).slice(0, 8)}
            rowKey={(row) => row.user_id}
            empty={<AdminEmpty icon="users" title={t("marketplace:shopadmin.none")} />}
            columns={[
              {
                key: "member",
                header: t("marketplace:shopadmin.col.member"),
                primary: true,
                render: (row) => (
                  <button type="button" className="mk-console__member" onClick={() => onMember(row.user_id)}>
                    {memberName(row.user_id)}
                  </button>
                ),
              },
              {
                key: "level",
                header: t("marketplace:shopadmin.col.level"),
                align: "end",
                render: (row) => row.level ?? 1,
              },
              { key: "xp", header: "XP", align: "end", render: (row) => format.number(row.xp) },
              {
                key: "coins",
                header: t("marketplace:shopadmin.col.coins"),
                align: "end",
                render: (row) => format.number(row.coins),
              },
            ]}
          />
        </AdminSection>
        <AdminSection title={t("marketplace:shopadmin.latest")} icon="clock" span="full" flush>
          <AdminTable
            label={t("marketplace:shopadmin.latest")}
            rows={data.activity}
            rowKey={(row) => `${row.kind}:${row.at}:${row.ownership_id ?? row.product}`}
            empty={<AdminEmpty icon="clock" title={t("marketplace:shopadmin.none")} />}
            columns={[
              {
                key: "at",
                header: t("marketplace:shopadmin.col.when"),
                render: (row) => format.dateTime(row.at),
              },
              {
                key: "kind",
                header: t("marketplace:shopadmin.col.what"),
                render: (row) => (
                  <StatusBadge tone={TONES[row.kind]}>
                    {t(`marketplace:shopadmin.kind.${row.kind}`)}
                  </StatusBadge>
                ),
              },
              {
                key: "product",
                header: t("marketplace:shopadmin.col.product"),
                primary: true,
                render: (row) => nameOf(row.names, row.product ?? ""),
              },
              {
                key: "member",
                header: t("marketplace:shopadmin.col.member"),
                render: (row) => (
                  <button type="button" className="mk-console__member" onClick={() => onMember(row.user_id)}>
                    {memberName(row.user_id)}
                  </button>
                ),
              },
              {
                key: "coins",
                header: t("marketplace:shopadmin.col.coins"),
                align: "end",
                render: (row) => (row.coins ? coins(row.coins) : "—"),
              },
            ]}
          />
        </AdminSection>
      </AdminGrid>
    </div>
  );
}
