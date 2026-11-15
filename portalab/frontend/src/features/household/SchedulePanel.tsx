import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { useNotify } from "../../design-system/components/Notification";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { useMeasures } from "../media/insights/api";
import {
  HOUSEHOLD_KEY,
  type Household,
  type HouseholdMember,
  type RestrictionSettings,
  useScreenTime,
  useUpdateProfile,
} from "./api";
import { ProfileFace } from "./ProfilePicker";
import { QuickTime } from "./QuickTime";
import { type Plan, ScreenPlanner, toMinutes } from "./ScreenPlanner";

/**
 * Issue 436: « Schedule » in My household — a profile's screen time as a calendar and the time it has left
 * now (the day's, the span's, the next span). Its master picks a profile, gives time in a tap and sets the
 * calendar in place; a profile reads its own.
 */
export function SchedulePanel({ household, onAdd }: { household: Household; onAdd: () => void }) {
  const t = useT();
  const [params, setParams] = useSearchParams();
  if (!household.can_manage) {
    const me = household.members.find((m) => m.id === household.me);
    if (!me?.restrictions) return <p className="household-note">{t("household:schedule.none")}</p>;
    return (
      <div className="schedule">
        <div className="schedule__layout">
          <Countdown member={me} profile={null} />
          <ScreenPlanner plan={me.restrictions} label={t("household:page.scheduleMineTitle")} />
        </div>
      </div>
    );
  }
  const profiles = household.members.filter((m) => m.kind !== "owner" && m.restrictions);
  if (!profiles.length)
    return (
      <p className="household-note">
        {t("household:schedule.noProfiles")}{" "}
        <Button variant="secondary" onClick={onAdd}>
          <Icon name="plus" size={14} />
          {t("household:page.add")}
        </Button>
      </p>
    );
  const chosen = profiles.find((p) => p.id === params.get("profile")) ?? (profiles[0] as HouseholdMember);
  return (
    <div className="schedule">
      {profiles.length > 1 ? (
        <fieldset className="schedule__who">
          <legend className="visually-hidden">{t("household:schedule.choose")}</legend>
          {profiles.map((profile) => (
            <button
              key={profile.id}
              type="button"
              aria-pressed={profile.id === chosen.id}
              data-active={profile.id === chosen.id || undefined}
              style={{ "--profile-color": profile.color } as React.CSSProperties}
              onClick={() => setParams({ profile: profile.id }, { replace: true })}
            >
              <ProfileFace member={profile} size="sm" />
              {profile.display_name}
            </button>
          ))}
        </fieldset>
      ) : null}
      <div className="schedule__layout">
        <div className="schedule__side">
          <Countdown member={chosen} profile={chosen.id} />
          <QuickTime member={chosen} />
        </div>
        <ScheduleEditor key={chosen.id} member={chosen} />
      </div>
    </div>
  );
}

/** The master's calendar of a profile: changed in place, saved (or undone) in one tap. */
function ScheduleEditor({ member }: { member: HouseholdMember }) {
  const t = useT();
  const notify = useNotify();
  const client = useQueryClient();
  const update = useUpdateProfile();
  const restrictions = member.restrictions as RestrictionSettings;
  const [draft, setDraft] = useState<Plan | null>(null);
  const save = () => {
    if (!draft) return;
    update.mutate(
      { id: member.id, restrictions: { ...restrictions, ...draft } },
      {
        onSuccess: async () => {
          await client.refetchQueries({ queryKey: HOUSEHOLD_KEY });
          setDraft(null);
          notify({
            severity: "success",
            title: t("household:schedule.saved", { name: member.display_name }),
          });
        },
        onError: () => notify({ severity: "critical", title: t("household:error") }),
      },
    );
  };
  return (
    <div className="schedule__calendar">
      <ScreenPlanner
        plan={draft ?? restrictions}
        onChange={setDraft}
        label={t("household:schedule.calendarOf", { name: member.display_name })}
      />
      {draft ? (
        <div className="schedule__save" role="status">
          <span>{t("household:schedule.unsaved")}</span>
          <Button variant="ghost" type="button" onClick={() => setDraft(null)}>
            {t("household:schedule.undo")}
          </Button>
          <Button type="button" disabled={update.isPending} onClick={save}>
            <Icon name="check" size={14} />
            {t("household:schedule.save")}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

type Tone = "free" | "open" | "low" | "closed";

/** The time a profile has left now: one big figure, then the day's and the span's, and today's spans. */
function Countdown({ member, profile }: { member: HouseholdMember; profile: string | null }) {
  const t = useT();
  const format = useFormat();
  const measures = useMeasures();
  const screen = useScreenTime(profile, true, true);
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(timer);
  }, []);
  const time = (minutes: number) => measures.duration(Math.max(0, minutes) * 60);
  const clock = now.getHours() * 60 + now.getMinutes();
  const wait = (hour: string) => time(toMinutes(hour) - clock);
  const until = member.free_until ? new Date(member.free_until) : null;
  const s = screen.data ?? null;
  let big = "∞";
  let caption = t("household:schedule.noLimit");
  let tone: Tone = "free";
  const rows: { label: string; value: string; ratio: number | null }[] = [];
  if (until && until > now) {
    caption = t("household:quick.freeUntil", { until: format.time(until) });
  } else if (s) {
    const next = s.next
      ? t("household:schedule.nextIn", { start: s.next.start, end: s.next.end, wait: wait(s.next.start) })
      : t("household:schedule.noneLeft");
    const candidates = [
      s.allowed !== null && s.allowed !== undefined ? s.allowed - s.used : null,
      s.slot?.allowed ? s.slot.allowed - s.slot.used : null,
      s.slot ? toMinutes(s.slot.end) - clock : null,
    ].filter((v): v is number => v !== null);
    const left = candidates.length ? Math.min(...candidates) : null;
    if (!s.open) [big, caption, tone] = [t("household:schedule.closed"), next, "closed"];
    else if (left !== null && left <= 0)
      [big, caption, tone] = [t("household:schedule.spent"), next, "closed"];
    else if (left !== null)
      [big, caption, tone] = [time(left), t("household:schedule.left"), left <= 15 ? "low" : "open"];
    if (s.allowed !== null && s.allowed !== undefined)
      rows.push({
        label: t("household:schedule.today"),
        value: t("household:schedule.of", { used: time(s.used), allowed: time(s.allowed) }),
        ratio: s.allowed ? s.used / s.allowed : 1,
      });
    if (s.slot)
      rows.push({
        label: t("household:schedule.span", { start: s.slot.start, end: s.slot.end }),
        value: s.slot.allowed
          ? t("household:schedule.of", { used: time(s.slot.used), allowed: time(s.slot.allowed) })
          : t("household:schedule.spanOpen", { end: s.slot.end, wait: wait(s.slot.end) }),
        ratio: s.slot.allowed ? s.slot.used / s.slot.allowed : null,
      });
  }
  return (
    <section
      className="schedule-count"
      data-tone={tone}
      aria-label={t("household:schedule.left")}
      aria-busy={screen.isPending || undefined}
    >
      <div className="schedule-count__main" aria-live="polite">
        <strong>{screen.isPending ? "…" : big}</strong>
        <span>{caption}</span>
      </div>
      {rows.length ? (
        <dl className="schedule-count__rows">
          {rows.map((row) => (
            <div key={row.label}>
              <dt>{row.label}</dt>
              <dd>{row.value}</dd>
              {row.ratio !== null ? (
                <span className="schedule-count__bar" aria-hidden="true">
                  <span style={{ inlineSize: `${Math.min(100, Math.round(row.ratio * 100))}%` }} />
                </span>
              ) : null}
            </div>
          ))}
        </dl>
      ) : null}
      {s && !(until && until > now) ? (
        <p className="schedule-count__spans">
          <Icon name="clock" size={14} />{" "}
          {t("household:schedule.spansToday", {
            spans: s.slots.length
              ? s.slots.map((span) => `${span.start}–${span.end}`).join(" · ")
              : t("household:schedule.noSpans"),
          })}
        </p>
      ) : null}
    </section>
  );
}
