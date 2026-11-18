import { useState } from "react";
import { Link } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { useMeasures } from "../media/insights/api";
import { type FamilyMember, type Household, type HouseholdMember, useFamilyActivity } from "./api";
import { ProfileFace } from "./ProfilePicker";

/**
 * Issue 428: « My household » as the family's dashboard — the household's week (or month) at a glance, then
 * each member: minutes watched, read or played, sittings, titles finished, days in a row, the kinds of
 * media, day by day, the last title, its level and coins; a restricted profile its screen time now.
 */
const PERIODS = [7, 30] as const;
const KINDS = ["movie", "series", "book", "audiobook", "comic", "manga", "music", "game"];

export function FamilyDashboard({ household }: { household: Household }) {
  const t = useT();
  const format = useFormat();
  const measures = useMeasures();
  const [days, setDays] = useState<(typeof PERIODS)[number]>(7);
  const activity = useFamilyActivity(days);
  const figures = new Map((activity.data?.members ?? []).map((m) => [m.user_id, m]));
  const total = (activity.data?.members ?? []).reduce(
    (sum, m) => ({
      minutes: sum.minutes + m.minutes,
      plays: sum.plays + m.plays,
      finished: sum.finished + m.finished,
    }),
    { minutes: 0, plays: 0, finished: 0 },
  );
  // issue 504: the play streak, as each one's « My progress » tells it — one number everywhere
  const best = [...household.members]
    .map((m) => ({ user_id: m.id, streak: m.progress.streak ?? 0 }))
    .sort((a, b) => b.streak - a.streak)[0];
  const nameOf = (id: string) => household.members.find((m) => m.id === id)?.display_name ?? "";
  return (
    <section className="family" aria-labelledby="family-title">
      <div className="family__head">
        <h2 id="family-title">{t("household:family.title")}</h2>
        <fieldset className="family__periods">
          <legend className="visually-hidden">{t("household:family.period")}</legend>
          {PERIODS.map((period) => (
            <button
              key={period}
              type="button"
              aria-pressed={days === period}
              data-active={days === period || undefined}
              onClick={() => setDays(period)}
            >
              {t("household:family.days", { days: period })}
            </button>
          ))}
        </fieldset>
      </div>
      <dl className="family__totals">
        <div>
          <dt>{t("household:family.time")}</dt>
          <dd>{measures.duration(total.minutes * 60)}</dd>
        </div>
        <div>
          <dt>{t("household:family.plays")}</dt>
          <dd>{format.number(total.plays)}</dd>
        </div>
        <div>
          <dt>{t("household:family.finished")}</dt>
          <dd>{format.number(total.finished)}</dd>
        </div>
        <div>
          <dt>{t("household:family.bestStreak")}</dt>
          <dd>
            {best && best.streak > 0
              ? t("household:family.streakOf", { days: best.streak, name: nameOf(best.user_id) })
              : "—"}
          </dd>
        </div>
      </dl>
      {activity.isError ? <p className="household-note">{t("household:family.unavailable")}</p> : null}
      <ul className="family__members">
        {household.members.map((member) => (
          <FamilyCard
            key={member.id}
            member={member}
            figures={figures.get(member.id)}
            days={days}
            me={member.id === household.me}
          />
        ))}
      </ul>
      <p className="family__more">
        <Link to="/media/insights?scope=household" className="ds-link">
          <Icon name="chart" size={14} /> {t("household:family.insights")}
        </Link>
      </p>
    </section>
  );
}

function FamilyCard({
  member,
  figures,
  days,
  me,
}: {
  member: HouseholdMember;
  figures: FamilyMember | undefined;
  days: number;
  me: boolean;
}) {
  const t = useT();
  const format = useFormat();
  const streak = member.progress.streak ?? 0; // issue 504: the play streak, as « My progress » tells it
  const measures = useMeasures();
  const series = figures?.series ?? [];
  const peak = Math.max(1, ...series);
  const kinds = Object.entries(figures?.kinds ?? {});
  const kindTotal = kinds.reduce((sum, [, minutes]) => sum + minutes, 0);
  const screen = figures?.screen;
  return (
    <li className="family-card" style={{ "--profile-color": member.color } as React.CSSProperties}>
      <div className="family-card__head">
        <ProfileFace member={member} size="md" />
        <div>
          <h3>
            {member.display_name}
            {me ? (
              <span className="household-badge household-badge--me">{t("household:page.you")}</span>
            ) : null}
          </h3>
          <span className="family-card__sub">
            {t("household:figures.level", { level: member.progress.level })} ·{" "}
            {t("household:family.coins", { coins: format.number(member.progress.coins) })} ·{" "}
            {t("household:family.xp", { xp: format.number(member.progress.xp) })}
          </span>
        </div>
        {streak > 0 ? (
          <span className="family-card__streak" title={t("household:family.streak", { days: streak })}>
            <Icon name="flame" size={16} />
            {streak}
            <span className="visually-hidden">{t("household:family.streak", { days: streak })}</span>
          </span>
        ) : null}
      </div>
      <dl className="family-card__figures">
        <div>
          <dt>{t("household:family.time")}</dt>
          <dd>{measures.duration((figures?.minutes ?? 0) * 60)}</dd>
        </div>
        <div>
          <dt>{t("household:family.plays")}</dt>
          <dd>{format.number(figures?.plays ?? 0)}</dd>
        </div>
        <div>
          <dt>{t("household:family.finished")}</dt>
          <dd>{format.number(figures?.finished ?? 0)}</dd>
        </div>
      </dl>
      <figure className="family-card__chart" data-days={days}>
        <figcaption className="visually-hidden">{t("household:family.byDay")}</figcaption>
        <div className="family-card__bars" aria-hidden="true">
          {series.map((minutes, index) => (
            <span
              // biome-ignore lint/suspicious/noArrayIndexKey: one bar a day, in order
              key={index}
              title={t("household:family.dayMinutes", { minutes, ago: series.length - 1 - index })}
              style={{ blockSize: `${Math.max(minutes ? 8 : 2, (minutes / peak) * 100)}%` }}
              data-today={index === series.length - 1 || undefined}
            />
          ))}
        </div>
      </figure>
      {kindTotal > 0 ? (
        <div className="family-card__kinds">
          <div className="family-card__kindbar" aria-hidden="true">
            {kinds.map(([kind, minutes]) => (
              <span
                key={kind}
                data-kind={KINDS.includes(kind) ? kind : "other"}
                style={{ inlineSize: `${(minutes / kindTotal) * 100}%` }}
              />
            ))}
          </div>
          <ul>
            {kinds.slice(0, 4).map(([kind, minutes]) => (
              <li key={kind} data-kind={KINDS.includes(kind) ? kind : "other"}>
                {t(`media:kind.${kind}`)} · {measures.duration(minutes * 60)}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="family-card__quiet">{t("household:family.nothing", { days })}</p>
      )}
      {figures?.last ? (
        <p className="family-card__last">
          <Icon name="clock" size={14} />{" "}
          {figures.last.object_id ? (
            <Link to={`/media/${figures.last.object_id}`}>{figures.last.title}</Link>
          ) : (
            figures.last.title
          )}{" "}
          <span>· {format.relative((new Date(figures.last.at).getTime() - Date.now()) / 1000)}</span>
        </p>
      ) : null}
      {screen ? (
        <p className="household-screen">
          <Icon name="clock" size={14} />{" "}
          {[
            screen.allowed !== null && screen.allowed !== undefined
              ? t("household:screen.today", { used: screen.used, allowed: screen.allowed })
              : null,
            screen.slot?.allowed
              ? t("household:screen.slot", { used: screen.slot.used, allowed: screen.slot.allowed })
              : screen.open === false
                ? t("household:screen.closed")
                : null,
          ]
            .filter(Boolean)
            .join(" · ") || t("household:family.screenFree")}
        </p>
      ) : null}
    </li>
  );
}
