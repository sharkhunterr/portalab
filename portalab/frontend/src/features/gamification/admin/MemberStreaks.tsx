import { AdminEmpty, AdminSection, AdminTable } from "../../../design-system/admin/AdminKit";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { heat, StreakDays, StreakMeter } from "../progression/StreakCard";
import { type MemberStreak, useMemberStreaks } from "./tuning";

/** Every member's play streak (027, issue 389): where it stands and burns, whether today already counts, its record,
 * its last fourteen days and the freezes the member holds — the longest streaks now first. */
export function MemberStreaks({ onMember }: { onMember?: (user: string) => void }) {
  const t = useT();
  const format = useFormat();
  const query = useMemberStreaks();
  const title = t("gamification:admin.streak.members");
  return (
    <AdminSection
      span="full"
      icon="users"
      title={title}
      description={t("gamification:admin.streak.membersHint")}
    >
      {query.isPending ? <FunctionalState state="loading" /> : null}
      {query.isError ? <FunctionalState state="unavailable" /> : null}
      {query.data ? (
        <AdminTable<MemberStreak>
          label={title}
          rows={query.data}
          rowKey={(row) => row.user_id}
          empty={<AdminEmpty icon="flame" title={t("gamification:admin.streak.noMembers")} />}
          columns={[
            {
              key: "member",
              header: t("gamification:admin.streak.member"),
              primary: true,
              render: (row) => {
                const name = row.name ?? t("gamification:admin.streak.unknown");
                return onMember ? (
                  <button type="button" className="ds-link" onClick={() => onMember(row.user_id)}>
                    {name}
                  </button>
                ) : (
                  name
                );
              },
            },
            {
              key: "days",
              header: t("gamification:admin.streak.current"),
              render: (row) => (
                <span className="streak-member">
                  <span className="streak-chip" data-heat={heat(row)}>
                    <Icon name="flame" size={14} />
                    {t("gamification:streak.days", { count: row.days })}
                    {row.multiplier > 1 ? <strong>×{row.multiplier}</strong> : null}
                  </span>
                  <StreakMeter streak={row} />
                </span>
              ),
            },
            {
              key: "today",
              header: t("gamification:admin.streak.today"),
              render: (row) =>
                row.days > 0 ? (
                  <span className="streak-today" data-risk={!row.today || undefined}>
                    <Icon name={row.today ? "check" : "clock"} size={14} />{" "}
                    {row.today
                      ? t("gamification:admin.streak.counted_")
                      : t("gamification:admin.streak.waiting")}
                  </span>
                ) : (
                  <span className="admin-muted">
                    {row.last_day ? format.date(`${row.last_day}T12:00:00Z`) : "—"}
                  </span>
                ),
            },
            {
              key: "recent",
              header: t("gamification:streak.recent"),
              render: (row) => <StreakDays days={row.recent ?? []} compact />,
            },
            {
              key: "best",
              header: t("gamification:streak.best"),
              align: "end",
              render: (row) => t("gamification:streak.days", { count: row.best ?? 0 }),
            },
            {
              key: "freezes",
              header: t("gamification:streak.freezes"),
              align: "end",
              render: (row) => format.number(row.freezes ?? 0),
            },
          ]}
        />
      ) : null}
    </AdminSection>
  );
}
