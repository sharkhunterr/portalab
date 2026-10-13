import { AdminEmpty, AdminSection, AdminTable } from "../../../design-system/admin/AdminKit";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { type MemberDetail, useMembersDetails } from "./tuning";

type Day = MemberDetail["days"][number];

/**
 * Issue 106 — the detail behind the charts, under the same member filter: every member's level (from the
 * start of the period to now), XP, Coins and Contribution held, gained and spent; or one member's, day by
 * day, with the levels reached.
 */
export function MemberDetails({
  days,
  member,
  onMember,
}: {
  days: number;
  member: string;
  onMember: (id: string) => void;
}) {
  const t = useT();
  const format = useFormat();
  const details = useMembersDetails(days);
  const all = details.data ?? [];
  const one = member ? all.find((m) => m.user_id === member) : undefined;
  const nameOf = (m: MemberDetail) => m.name ?? m.user_id.slice(0, 8);
  const signed = (n: number) => (n > 0 ? `+${format.number(n)}` : n < 0 ? format.number(n) : "—");
  const value = (gained: number, balance: number, spent = 0) => (
    <span className="gam-detail">
      <strong>{signed(gained)}</strong>
      {spent ? <span className="gam-detail__spent">−{format.number(spent)}</span> : null}
      <span className="admin-muted">
        {t("gamification:admin.details.held", { amount: format.number(balance) })}
      </span>
    </span>
  );
  const title = one
    ? t("gamification:admin.details.oneTitle", { name: nameOf(one) })
    : t("gamification:admin.details.title");
  return (
    <AdminSection
      span="full"
      icon="list"
      title={title}
      description={t("gamification:admin.details.hint", { days })}
      flush
    >
      {details.isPending ? <FunctionalState state="loading" /> : null}
      {details.isError ? <FunctionalState state="unavailable" onRetry={() => details.refetch()} /> : null}
      {details.data && !one ? (
        <AdminTable
          label={title}
          rows={member ? [] : all}
          rowKey={(row) => row.user_id}
          empty={<AdminEmpty icon="users" title={t("gamification:admin.overview.empty")} />}
          columns={[
            {
              key: "member",
              header: t("gamification:admin.overview.member"),
              primary: true,
              render: (row) => (
                <button type="button" className="ds-link" onClick={() => onMember(row.user_id)}>
                  {nameOf(row)}
                </button>
              ),
            },
            {
              key: "level",
              header: t("gamification:admin.details.level"),
              render: (row) =>
                row.level > row.start_level
                  ? t("gamification:admin.details.levelUp", {
                      from: row.start_level,
                      to: row.level,
                      count: row.level - row.start_level,
                    })
                  : String(row.level),
            },
            { key: "xp", header: "XP", align: "end", render: (row) => value(row.xp.gained, row.xp.balance) },
            {
              key: "coins",
              header: t("gamification:value.coins"),
              align: "end",
              render: (row) => value(row.coins.gained, row.coins.balance, row.coins.spent),
            },
            {
              key: "contribution",
              header: t("gamification:value.contribution"),
              align: "end",
              render: (row) => value(row.contribution.gained, row.contribution.balance),
            },
          ]}
        />
      ) : null}
      {one ? (
        <>
          <p className="gam-detail__summary">
            {t("gamification:admin.details.summary", {
              level: one.level,
              xp: format.number(one.xp.balance),
              coins: format.number(one.coins.balance),
              contribution: format.number(one.contribution.balance),
            })}
          </p>
          <AdminTable<Day>
            label={title}
            rows={[...one.days].reverse()}
            rowKey={(row) => row.day}
            empty={<AdminEmpty icon="clock" title={t("gamification:admin.overview.empty")} />}
            columns={[
              {
                key: "day",
                header: t("gamification:admin.overview.day"),
                primary: true,
                render: (row) => format.date(`${row.day}T12:00:00Z`, "medium"),
              },
              { key: "xp", header: "XP", align: "end", render: (row) => signed(row.xp) },
              {
                key: "levels",
                header: t("gamification:admin.details.levels"),
                render: (row) =>
                  row.levels.length
                    ? row.levels.map((n) => t("gamification:admin.details.levelN", { level: n })).join(", ")
                    : "—",
              },
              {
                key: "coins",
                header: t("gamification:admin.details.coinsGained"),
                align: "end",
                render: (row) => signed(row.coins),
              },
              {
                key: "spent",
                header: t("gamification:admin.details.coinsSpent"),
                align: "end",
                render: (row) => (row.spent_coins ? `−${format.number(row.spent_coins)}` : "—"),
              },
              {
                key: "contribution",
                header: t("gamification:value.contribution"),
                align: "end",
                render: (row) => signed(row.contribution),
              },
            ]}
          />
        </>
      ) : null}
    </AdminSection>
  );
}
