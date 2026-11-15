import { useState } from "react";
import { Link, Navigate } from "react-router";
import { Button } from "../../design-system/components/Button";
import { TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { useNotify } from "../../design-system/components/Notification";
import { Dialog, DialogActions } from "../../design-system/components/Overlays";
import { PageHeader } from "../../design-system/components/PageHeader";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { ApiError } from "../../state/regions";
import {
  type AccessRequest,
  chooseProfile,
  type Household,
  type HouseholdMember,
  useAccessRequests,
  useDecideAccess,
  useHousehold,
  useProfileActivity,
  useScreenTime,
  useSetPin,
} from "./api";
import { FamilyDashboard } from "./FamilyDashboard";
import { HouseholdEconomyChoice } from "./HouseholdEconomy";
import { ProfileEditor } from "./ProfileEditor";
import { ProfileFace } from "./ProfilePicker";
import { QuickTime } from "./QuickTime";
import { SchedulePanel } from "./SchedulePanel";
import "./household.css";

/**
 * « My household » (spec 032): every household member sees the wallet the household shares (the master's
 * balances hold every profile's earnings) and each member's figures; the master adds and sets profiles,
 * reads their activity and answers their access requests.
 */
export type HouseholdView = "overview" | "profiles" | "schedule" | "requests";

export default function HouseholdPage({ view = "overview" }: { view?: HouseholdView }) {
  const t = useT();
  const household = useHousehold();
  const requests = useAccessRequests();
  const [editing, setEditing] = useState<HouseholdMember | "new" | null>(null);
  const [watching, setWatching] = useState<HouseholdMember | null>(null);
  const [pinOf, setPinOf] = useState<HouseholdMember | null>(null);
  // issue 428: the old « ?tab=requests » links open the requests tab
  if (view === "overview" && new URLSearchParams(globalThis.location?.search).get("tab") === "requests")
    return <Navigate to="/household/requests" replace />;
  if (household.isPending) return <FunctionalState state="loading" />;
  if (household.isError || !household.data)
    return <FunctionalState state="unavailable" onRetry={() => household.refetch()} />;
  const data = household.data;
  const profiles = data.members.filter((m) => m.kind !== "owner");
  const pending = (requests.data ?? []).filter((r) => r.status === "pending").length;
  // issue 436: a profile reads its own schedule
  const heading = view === "schedule" && !data.can_manage ? "scheduleMine" : view;
  const icons = { overview: "dashboard", profiles: "user", schedule: "calendar-week", requests: "key" };
  return (
    <div className="household-page">
      <PageHeader
        title={t(`household:page.${heading}Title`)}
        context={t(`household:page.${heading}Subtitle`)}
        icon={icons[view]}
        primary={
          data.can_manage && profiles.length < data.max_profiles ? (
            <Button onClick={() => setEditing("new")}>
              <Icon name="plus" size={16} />
              {t("household:page.add")}
            </Button>
          ) : undefined
        }
        secondary={
          data.members.length > 1 ? (
            <Button variant="secondary" onClick={() => chooseProfile()}>
              <Icon name="users" size={16} />
              {t("household:switch")}
            </Button>
          ) : undefined
        }
      />
      {!data.enabled ? <p className="household-note">{t("household:page.disabled")}</p> : null}
      {data.can_manage && profiles.length > 0 && !data.members[0]?.has_pin ? (
        <p className="household-advice" role="note">
          <Icon name="key" size={16} />
          {t("household:page.pinAdvice")}
          <Button variant="secondary" onClick={() => data.members[0] && setPinOf(data.members[0])}>
            {t("household:page.myPin")}
          </Button>
        </p>
      ) : null}
      {view === "overview" ? (
        <>
          <Wallet household={data} />
          {data.can_manage && pending ? (
            <p className="household-advice" role="note">
              <Icon name="key" size={16} />
              {t("household:family.pending", { count: pending })}
              <Link className="ds-button ds-button--secondary" to="/household/requests">
                {t("household:family.answer")}
              </Link>
            </p>
          ) : null}
          {profiles.length === 0 && data.can_manage ? (
            <p className="household-note">
              {t("household:page.empty")}{" "}
              <Link to="/household/profiles" className="ds-link">
                {t("household:page.add")}
              </Link>
            </p>
          ) : null}
          <FamilyDashboard household={data} />
        </>
      ) : view === "profiles" ? (
        <>
          <HouseholdEconomyChoice household={data} />
          <p className="household-count">
            {t("household:page.count", { count: profiles.length, max: data.max_profiles })}
          </p>
          {profiles.length === 0 && data.can_manage ? (
            <p className="household-note">{t("household:page.empty")}</p>
          ) : null}
          <ul className="household-members">
            {data.members.map((member) => (
              <MemberCard
                key={member.id}
                member={member}
                me={member.id === data.me}
                manage={data.can_manage && member.kind !== "owner"}
                economy={data.economy ?? "pot"}
                onEdit={() => setEditing(member)}
                onActivity={() => setWatching(member)}
                onPin={() => setPinOf(member)}
              />
            ))}
          </ul>
        </>
      ) : view === "schedule" ? (
        <SchedulePanel household={data} onAdd={() => setEditing("new")} />
      ) : (
        <Requests items={requests.data ?? []} household={data} />
      )}
      {editing ? (
        <ProfileEditor
          member={editing === "new" ? null : editing}
          position={profiles.length + 1}
          palette={data.palette}
          economy={data.economy ?? "pot"}
          onClose={() => setEditing(null)}
        />
      ) : null}
      {watching ? <Activity member={watching} onClose={() => setWatching(null)} /> : null}
      {pinOf ? <MyPin member={pinOf} asMaster={data.can_manage} onClose={() => setPinOf(null)} /> : null}
    </div>
  );
}

function Wallet({ household }: { household: Household }) {
  const t = useT();
  const format = useFormat();
  const totals = household.totals;
  if (!totals) return null;
  return (
    <section className="household-wallet" aria-labelledby="household-wallet">
      <div className="household-wallet__coins">
        <Icon name="coins" size={28} />
        <div>
          <h2 id="household-wallet">{t("household:page.totals")}</h2>
          <strong>{format.number(totals.coins)}</strong> <span>{t("household:figures.coins")}</span>
        </div>
      </div>
      <dl className="household-wallet__figures">
        <div>
          <dt>{t("household:figures.xp")}</dt>
          <dd>{format.number(totals.xp)}</dd>
        </div>
        <div>
          <dt>{t("household:figures.contribution")}</dt>
          <dd>{format.number(totals.contribution)}</dd>
        </div>
        <div>
          <dt>
            <Icon name="star" size={14} />
          </dt>
          <dd>{t("household:figures.level", { level: totals.level })}</dd>
        </div>
      </dl>
      <p className="household-wallet__hint">{t("household:page.totalsHint")}</p>
    </section>
  );
}

function MemberCard({
  member,
  me,
  manage,
  economy,
  onEdit,
  onActivity,
  onPin,
}: {
  member: HouseholdMember;
  me: boolean;
  manage: boolean;
  economy: string;
  onEdit: () => void;
  onActivity: () => void;
  onPin: () => void;
}) {
  const t = useT();
  const format = useFormat();
  const restricted = member.restrictions;
  const age = member.effective_age ?? null; // 032: from its birth date, else the fixed one
  const limited = restricted && (age !== null || (restricted.blocked ?? []).length > 0);
  return (
    <li className="household-member" style={{ "--profile-color": member.color } as React.CSSProperties}>
      <div className="household-member__head">
        <ProfileFace member={member} size="md" />
        <div>
          <h3>
            {member.display_name}
            {me ? (
              <span className="household-badge household-badge--me">{t("household:page.you")}</span>
            ) : null}
          </h3>
          <span className="household-member__kind">
            {member.kind === "owner" ? <Icon name="crown" size={14} /> : null}
            {t(`household:kind.${member.kind}`)}
            {typeof member.age === "number" ? ` · ${t("household:page.age", { age: member.age })}` : ""}
            {` · ${t("household:figures.level", { level: member.progress.level })}`}
          </span>
        </div>
      </div>
      <dl className="household-member__figures">
        <div>
          <dt>{t("household:figures.xp")}</dt>
          <dd>{format.number(member.progress.xp)}</dd>
        </div>
        <div>
          <dt>{t("household:figures.coins")}</dt>
          <dd>{format.number(member.progress.coins)}</dd>
        </div>
        <div>
          <dt>{t("household:figures.contribution")}</dt>
          <dd>{format.number(member.progress.contribution)}</dd>
        </div>
      </dl>
      {member.restrictions?.daily_minutes ||
      member.restrictions?.week_minutes ||
      member.restrictions?.slots?.length ? (
        <ScreenLine member={member} />
      ) : null}
      <div className="household-member__badges">
        {limited ? (
          <span className="household-badge">
            <Icon name="shield" size={12} />
            {t("household:page.restricted", { age: age ?? "none" })}
          </span>
        ) : null}
        {member.kind !== "owner" && (economy === "pot" || !member.community_visible) ? (
          <span className="household-badge">
            <Icon name="hide" size={12} />
            {t(economy === "pot" ? "household:page.private" : "household:page.anonymous")}
          </span>
        ) : null}
        {member.has_pin ? (
          <span className="household-badge">
            <Icon name="lock" size={12} />
            {t("household:picker.locked")}
          </span>
        ) : null}
      </div>
      {manage && member.restrictions ? <QuickTime member={member} /> : null}
      <div className="household-member__actions">
        {manage ? (
          <>
            <Button variant="secondary" onClick={onEdit}>
              <Icon name="settings" size={16} />
              {t("household:page.edit", { name: member.display_name })}
            </Button>
            <Button variant="ghost" onClick={onActivity}>
              <Icon name="activity" size={16} />
              {t("household:page.activity", { name: member.display_name })}
            </Button>
          </>
        ) : null}
        {me ? (
          <Button variant="ghost" onClick={onPin}>
            <Icon name="key" size={16} />
            {t("household:page.myPin")}
          </Button>
        ) : null}
      </div>
    </li>
  );
}

function Activity({ member, onClose }: { member: HouseholdMember; onClose: () => void }) {
  const t = useT();
  const format = useFormat();
  const activity = useProfileActivity(member.id);
  const data = activity.data;
  return (
    <Dialog
      trigger={null}
      open
      onOpenChange={(open) => (open ? undefined : onClose())}
      title={t("household:page.activity", { name: member.display_name })}
      closeLabel={t("household:editor.cancel")}
    >
      {activity.isPending ? <FunctionalState state="loading" /> : null}
      {activity.isError ? <FunctionalState state="unavailable" onRetry={() => activity.refetch()} /> : null}
      {data ? (
        <div className="household-activity">
          <p>
            {data.last_seen_at
              ? t("household:activity.seen", { date: format.dateTime(data.last_seen_at) })
              : t("household:activity.never")}
          </p>
          <h3>{t("household:activity.economy")}</h3>
          {data.economy.length === 0 ? <p>{t("household:activity.empty")}</p> : null}
          <ul className="household-activity__lines">
            {data.economy.map((line) => (
              <li
                key={`${line.at}-${line.value}-${line.delta}-${line.source}`}
                data-gain={line.delta > 0 || undefined}
              >
                <span className="household-activity__delta">
                  {line.delta > 0 ? "+" : ""}
                  {t("household:activity.line", {
                    delta: line.delta,
                    value: t(
                      `household:figures.${line.value === "coins" ? "coins" : line.value === "xp" ? "xp" : "contribution"}`,
                    ),
                  })}
                </span>
                <span>{line.rule ?? line.reason ?? line.source}</span>
                <time dateTime={line.at}>{format.dateTime(line.at)}</time>
              </li>
            ))}
          </ul>
          <h3>{t("household:activity.requests")}</h3>
          {data.requests.length === 0 ? <p>{t("household:requests.empty")}</p> : null}
          <ul className="household-requests">
            {data.requests.map((request) => (
              <RequestLine key={request.id} request={request} />
            ))}
          </ul>
        </div>
      ) : null}
    </Dialog>
  );
}

function RequestLine({ request, children }: { request: AccessRequest; children?: React.ReactNode }) {
  const t = useT();
  const format = useFormat();
  return (
    <li className="household-request" data-status={request.status}>
      <Icon name="lock" size={18} />
      <div>
        <strong>{t("household:requests.asks", { name: request.profile_name, title: request.title })}</strong>
        <span className="household-request__meta">
          {request.rating ? `${t("household:requests.rating", { rating: request.rating })} · ` : null}
          {format.dateTime(request.created_at)}
          {request.note ? ` · « ${request.note} »` : null}
        </span>
      </div>
      <span className="household-badge" data-status={request.status}>
        {t(`household:requests.${request.status}`)}
        {request.status === "approved" && request.expires_at
          ? ` ${t("household:requests.until", { date: format.date(request.expires_at, "medium") })}`
          : null}
      </span>
      {children}
    </li>
  );
}

function Requests({ items, household }: { items: AccessRequest[]; household: Household }) {
  const t = useT();
  const decide = useDecideAccess();
  if (items.length === 0) return <p className="household-note">{t("household:requests.empty")}</p>;
  return (
    <ul className="household-requests">
      {items.map((request) => (
        <RequestLine key={request.id} request={request}>
          {household.can_manage && request.status === "pending" ? (
            <span className="household-request__actions">
              <Button
                onClick={() => decide.mutate({ id: request.id, approve: true })}
                disabled={decide.isPending}
              >
                <Icon name="check" size={16} />
                {t("household:requests.approve")}
              </Button>
              <Button
                variant="secondary"
                onClick={() => decide.mutate({ id: request.id, approve: true, days: 1 })}
                disabled={decide.isPending}
              >
                <Icon name="clock" size={16} />
                {t("household:requests.approveFor", { days: 1 })}
              </Button>
              <Button
                variant="ghost"
                onClick={() => decide.mutate({ id: request.id, approve: false })}
                disabled={decide.isPending}
              >
                {t("household:requests.deny")}
              </Button>
            </span>
          ) : null}
        </RequestLine>
      ))}
    </ul>
  );
}

function MyPin({
  member,
  asMaster,
  onClose,
}: {
  member: HouseholdMember;
  asMaster: boolean;
  onClose: () => void;
}) {
  const t = useT();
  const notify = useNotify();
  const setPin = useSetPin();
  const [current, setCurrent] = useState("");
  const [pin, setPinValue] = useState("");
  const asksCurrent = member.has_pin && !asMaster;
  const invalid = pin !== "" && !/^\d{4,6}$/.test(pin);
  const problem = setPin.error instanceof ApiError ? setPin.error : null;
  return (
    <Dialog
      trigger={null}
      open
      onOpenChange={(open) => (open ? undefined : onClose())}
      title={t("household:page.myPin")}
      closeLabel={t("household:editor.cancel")}
    >
      <form
        className="household-editor"
        onSubmit={(event) => {
          event.preventDefault();
          if (invalid) return;
          setPin.mutate(
            { id: member.id, pin: pin || null, ...(asksCurrent ? { current } : {}) },
            {
              onSuccess: () => {
                notify({ severity: "success", title: t("household:myPin.saved") });
                onClose();
              },
            },
          );
        }}
      >
        {asksCurrent ? (
          <TextField
            label={t("household:myPin.current")}
            type="password"
            inputMode="numeric"
            autoComplete="off"
            maxLength={6}
            value={current}
            onChange={(event) => setCurrent(event.target.value.replace(/\D/g, ""))}
          />
        ) : null}
        <TextField
          label={t("household:myPin.new")}
          hint={t("household:myPin.hint")}
          type="password"
          inputMode="numeric"
          autoComplete="new-password"
          maxLength={6}
          value={pin}
          error={invalid ? t("household:pin.hint") : undefined}
          onChange={(event) => setPinValue(event.target.value.replace(/\D/g, ""))}
        />
        {problem ? (
          <p role="alert" className="household-error">
            {problem.code === "household.wrong_pin" ? t("household:pin.wrong") : t("household:error")}
          </p>
        ) : null}
        <DialogActions>
          <Button type="submit" disabled={setPin.isPending || invalid}>
            {t("household:editor.save")}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

/** 032: how much of its screen time a profile spent today — 432: and its span now, or the next one. */
function ScreenLine({ member }: { member: HouseholdMember }) {
  const t = useT();
  const screen = useScreenTime(member.id).data;
  if (!screen) return null;
  const parts = [
    screen.allowed !== null && screen.allowed !== undefined
      ? t("household:screen.today", { used: screen.used, allowed: screen.allowed })
      : null,
    screen.slot
      ? screen.slot.allowed
        ? t("household:screen.slot", { used: screen.slot.used, allowed: screen.slot.allowed })
        : t("household:screen.slotOpen", { end: screen.slot.end })
      : screen.open === false
        ? t("household:screen.closed")
        : null,
    !screen.slot && screen.next
      ? t("household:screen.next", { start: screen.next.start, end: screen.next.end })
      : null,
  ].filter(Boolean);
  if (!parts.length) return null;
  return (
    <p className="household-screen">
      <Icon name="clock" size={14} /> {parts.join(" · ")}
    </p>
  );
}
