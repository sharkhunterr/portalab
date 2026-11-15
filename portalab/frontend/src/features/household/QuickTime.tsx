import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { useNotify } from "../../design-system/components/Notification";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { EXTRA_MINUTES, type HouseholdMember, minutesLeftToday, useFreeProfile, useGiveMinutes } from "./api";

/** Issue 432: time given in a few taps — minutes more today, no limits for a while, the limits back. */
export function QuickTime({ member }: { member: HouseholdMember }) {
  const t = useT();
  const format = useFormat();
  const notify = useNotify();
  const give = useGiveMinutes();
  const free = useFreeProfile();
  const name = member.display_name;
  const until = member.free_until ? new Date(member.free_until) : null;
  const freed = until !== null && until.getTime() > Date.now();
  const timed = Boolean(
    member.restrictions?.daily_minutes ||
      member.restrictions?.week_minutes ||
      member.restrictions?.slots?.length,
  );
  const failed = () => notify({ severity: "critical", title: t("household:error") });
  const freeFor = (minutes: number) =>
    free.mutate(
      { id: member.id, minutes },
      {
        onSuccess: () =>
          notify({
            severity: "success",
            title: t("household:quick.freed", {
              name,
              until: format.time(new Date(Date.now() + minutes * 60_000)),
            }),
          }),
        onError: failed,
      },
    );
  return (
    <section className="household-quick" aria-label={t("household:quick.title")}>
      {freed ? (
        <div className="household-quick__row">
          <span className="household-badge household-badge--free">
            <Icon name="infinity" size={12} />
            {t("household:quick.freeUntil", { until: format.time(until) })}
          </span>
          <Button
            variant="ghost"
            disabled={free.isPending}
            onClick={() =>
              free.mutate(
                { id: member.id, minutes: null },
                {
                  onSuccess: () =>
                    notify({ severity: "success", title: t("household:quick.backDone", { name }) }),
                  onError: failed,
                },
              )
            }
          >
            <Icon name="lock" size={14} />
            {t("household:quick.back")}
          </Button>
        </div>
      ) : (
        <>
          {timed ? (
            <div className="household-quick__row">
              <span className="household-quick__label">
                {t("household:quick.more")}
                {member.bonus_minutes
                  ? ` (${t("household:quick.bonus", { minutes: member.bonus_minutes })})`
                  : ""}
              </span>
              {EXTRA_MINUTES.map((minutes) => (
                <Button
                  key={minutes}
                  variant="secondary"
                  disabled={give.isPending}
                  onClick={() =>
                    give.mutate(
                      { id: member.id, minutes },
                      {
                        onSuccess: () =>
                          notify({
                            severity: "success",
                            title: t("household:quick.given", { minutes, name }),
                          }),
                        onError: failed,
                      },
                    )
                  }
                >
                  {t("household:quick.minutes", { minutes })}
                </Button>
              ))}
            </div>
          ) : null}
          <div className="household-quick__row">
            <span className="household-quick__label">{t("household:quick.free")}</span>
            {[1, 2].map((hours) => (
              <Button
                key={hours}
                variant="secondary"
                disabled={free.isPending}
                onClick={() => freeFor(hours * 60)}
              >
                {t("household:quick.freeFor", { hours })}
              </Button>
            ))}
            <Button variant="secondary" disabled={free.isPending} onClick={() => freeFor(minutesLeftToday())}>
              {t("household:quick.freeDay")}
            </Button>
          </div>
        </>
      )}
    </section>
  );
}
