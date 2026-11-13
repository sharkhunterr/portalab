import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import {
  AdminEmpty,
  AdminPage,
  AdminSection,
  AdminTabs,
  KeyValues,
  StatusBadge,
} from "../../../design-system/admin/AdminKit";
import { Avatar } from "../../../design-system/components/Avatar";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { AnomalyQueue } from "../../gamification/admin/AnomalyQueue";
import { MemberDetails } from "../../gamification/admin/MemberDetails";
import { Operations } from "../../gamification/admin/Operations";
import "../../gamification/gamification.css";
import { PlaysByKind } from "../../gamification/progression/PlaysByKind";
import { MemberConsole } from "../../marketplace/admin/console/Members";
import { RequestsQueue } from "../../marketplace/admin/RequestsQueue";
import "../../marketplace/marketplace.css";
import { MemberFeedback } from "../../support/feedback/ReviewQueue";
import "../../support/support.css";
import { useQueue } from "../../support/tickets/api";
import { TicketList } from "../../support/tickets/MyTickets";
import "../admin.css";
import { MediaRequestsList } from "../media/RequestsAdmin";
import { MemberPassword, MemberProfileForm, MemberRoles, MemberTwoFactor } from "./MemberEdit";
import { allMembers, InviteLink, MEMBERS_KEY, type Member, MemberActions, STATE_TONE } from "./MembersAdmin";
import { MemberServiceAccounts } from "./ServiceAccountsPanel";

/**
 * One member's card for the administrators (``/admin/members/:userId``): everything about them that was
 * spread over the members list, the shop console, the gamification overview, the request queues and the
 * support desk, in tabs — each tab reuses the page it comes from, filtered to this member.
 */
const TABS = ["profile", "economy", "progression", "requests", "support", "vigilance", "accounts"] as const;
type Tab = (typeof TABS)[number];
const PERIODS = [7, 30, 90, 365];

export default function MemberCard() {
  const t = useT();
  const format = useFormat();
  const { userId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const asked = params.get("tab");
  const tab: Tab = TABS.includes(asked as Tab) ? (asked as Tab) : "profile";
  // the members list is shared with the members page: opened from there, it is already loaded
  const members = useQuery({ queryKey: MEMBERS_KEY, queryFn: allMembers });
  const member = members.data?.find((m) => m.id === userId);
  const back = (
    <Link to="/admin/members" className="ds-button ds-button--ghost">
      <Icon name="chevron-left" size={16} />
      {t("admin:memberCard.back")}
    </Link>
  );
  if (!member) {
    return (
      <AdminPage icon="user" title={t("admin:members.member")} secondary={back}>
        {members.isPending ? <FunctionalState state="loading" /> : null}
        {members.isError ? <FunctionalState state="unavailable" onRetry={() => members.refetch()} /> : null}
        {members.isSuccess ? <AdminEmpty icon="user" title={t("admin:memberCard.notFound")} /> : null}
      </AdminPage>
    );
  }
  const name = member.display_name ?? member.login ?? userId.slice(0, 8);
  return (
    <AdminPage
      icon="user"
      title={name}
      wide
      description={
        <span className="member-card__identity">
          <Avatar name={name} userId={member.id} size="sm" decorative />
          <span>
            @{member.login}
            {member.email ? ` · ${member.email}` : ""}
          </span>
          <StatusBadge tone={STATE_TONE[member.state] ?? "neutral"}>
            {t(`admin:members.state.${member.state}`)}
          </StatusBadge>
          <span className="admin-muted">
            {t("admin:members.created")} {format.date(member.created_at, "medium")}
          </span>
        </span>
      }
      secondary={back}
      tabs={
        <AdminTabs
          label={name}
          current={tab}
          onChange={(next) => setParams(next === "profile" ? {} : { tab: next }, { replace: true })}
          tabs={TABS.map((key) => ({ key, label: t(`admin:memberCard.tabs.${key}`) }))}
        />
      }
    >
      {tab === "profile" ? <ProfileTab member={member} /> : null}
      {tab === "economy" ? <MemberConsole key={userId} userId={userId} name={name} inCard /> : null}
      {tab === "progression" ? <ProgressionTab userId={userId} name={name} /> : null}
      {tab === "requests" ? <RequestsTab userId={userId} /> : null}
      {tab === "support" ? <SupportTab userId={userId} /> : null}
      {tab === "vigilance" ? <VigilanceTab member={member} /> : null}
      {tab === "accounts" ? <MemberServiceAccounts userId={userId} name={name} /> : null}
    </AdminPage>
  );
}

/** The account itself: its state and dates, what the « Edit » dialog changes, the password (issue 348), the
 * roles, the actions. */
function ProfileTab({ member }: { member: Member }) {
  const t = useT();
  const format = useFormat();
  const client = useQueryClient();
  const [link, setLink] = useState<string | null>(null);
  const ago = (iso: string | null) => (iso ? format.relative((Date.parse(iso) - Date.now()) / 1000) : "—");
  return (
    <>
      <AdminSection
        title={t("admin:memberCard.account")}
        icon="shield"
        actions={
          <span className="member-card__actions">
            <MemberActions key={member.state} member={member} onLink={setLink} edit={false} />
          </span>
        }
      >
        <KeyValues
          items={[
            {
              key: "state",
              label: t("admin:members.stateColumn"),
              value: (
                <StatusBadge tone={STATE_TONE[member.state] ?? "neutral"}>
                  {t(`admin:members.state.${member.state}`)}
                </StatusBadge>
              ),
            },
            { key: "created", label: t("admin:members.created"), value: ago(member.created_at) },
            { key: "seen", label: t("admin:members.lastSeen"), value: ago(member.last_sign_in_at) },
          ]}
        />
        {link ? <InviteLink token={link} /> : null}
      </AdminSection>
      <AdminSection title={t("admin:memberCard.identity")} icon="user">
        <MemberProfileForm
          key={member.id}
          member={member}
          onSaved={() => void client.invalidateQueries({ queryKey: MEMBERS_KEY })}
        />
      </AdminSection>
      <MemberPassword member={member} />
      <MemberTwoFactor member={member} />
      <MemberRoles member={member} />
    </>
  );
}

/** The gamification overview's journal, detail and plays — under this member's filter. */
function ProgressionTab({ userId, name }: { userId: string; name: string }) {
  const t = useT();
  const [days, setDays] = useState(30);
  return (
    <>
      <AdminTabs
        label={t("admin:memberCard.period")}
        current={String(days)}
        onChange={(next) => setDays(Number(next))}
        tabs={PERIODS.map((p) => ({
          key: String(p),
          label: t("gamification:admin.overview.days", { days: p }),
        }))}
      />
      <Operations days={days} member={userId} memberName={name} />
      <MemberDetails days={days} member={userId} onMember={() => undefined} />
      <PlaysByKind admin days={days} member={userId} />
    </>
  );
}

/** What they asked for: the shop's requests to handle and their media requests. */
function RequestsTab({ userId }: { userId: string }) {
  const t = useT();
  return (
    <>
      <RequestsQueue userId={userId} />
      <AdminSection title={t("media:moderation.title")} icon="film" description={t("media:moderation.pitch")}>
        <MediaRequestsList tab="all" userId={userId} />
      </AdminSection>
    </>
  );
}

/** Their tickets (every state) and their feedback. */
function SupportTab({ userId }: { userId: string }) {
  const t = useT();
  const tickets = useQueue({ requester: userId });
  const items = tickets.data?.items ?? [];
  return (
    <>
      <AdminSection
        title={t("support:queue.title")}
        icon="life-buoy"
        description={tickets.data ? t("support:queue.count", { count: items.length }) : undefined}
        flush={items.length > 0}
      >
        {tickets.isPending ? <FunctionalState state="loading" /> : null}
        {tickets.isError ? <FunctionalState state="unauthorized" /> : null}
        {tickets.data && !items.length ? <p className="admin-muted">{t("support:queue.empty")}</p> : null}
        {items.length ? (
          <TicketList items={items} label={t("support:queue.title")} base="/support/queue" />
        ) : null}
      </AdminSection>
      <AdminSection title={t("support:review.title")} icon="message">
        <MemberFeedback userId={userId} />
      </AdminSection>
    </>
  );
}

/** Rewards withheld from them for review, and whether the account is suspended. */
function VigilanceTab({ member }: { member: Member }) {
  const t = useT();
  const [link, setLink] = useState<string | null>(null);
  return (
    <>
      <AdminSection
        title={t("admin:memberCard.suspension")}
        icon="lock"
        description={t("admin:memberCard.suspensionHint")}
        actions={
          <span className="member-card__actions">
            <MemberActions member={member} onLink={setLink} edit={false} suspensionOnly />
          </span>
        }
      >
        <StatusBadge tone={STATE_TONE[member.state] ?? "neutral"}>
          {t(`admin:members.state.${member.state}`)}
        </StatusBadge>
        {link ? <InviteLink token={link} /> : null}
      </AdminSection>
      <AnomalyQueue userId={member.id} />
    </>
  );
}
