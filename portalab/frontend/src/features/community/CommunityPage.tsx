import { NavLink, useParams } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { QuestBoard } from "./achievements/QuestBoard";
import { Showcase } from "./achievements/Showcase";
import { EventList } from "./events/EventList";
import { Feed } from "./feed/Feed";
import { LeaderboardPage } from "./leaderboards/LeaderboardPage";
import { Directory } from "./members/Directory";
import { CommunityOverview } from "./overview/CommunityOverview";
import { ProfilePage } from "./profile/ProfilePage";
import { ProposalDetail } from "./projects/ProposalDetail";
import { ProposalList } from "./projects/ProposalList";
import "./community.css";
import { PageHeader } from "../../design-system/components/PageHeader";

// #63: the overview, then one tab per thing to look at; the activity, proposals and events stay reachable
// from the overview's panels (and the calendar), without tabs of their own
const TABS = [
  { to: "/community", key: "discover", end: true, icon: "compass" },
  { to: "/community/leaderboards", key: "leaderboards", end: true, icon: "medal" },
  { to: "/community/quests", key: "quests", end: true, icon: "target" },
  { to: "/community/achievements", key: "achievements", end: true, icon: "trophy" },
  { to: "/community/members", key: "members", end: true, icon: "users" },
] as const;

/** ``/community/*`` (spec 012, slice A): discovery, members, activity and events. */
export default function CommunityPage({
  view,
}: {
  view:
    | "discover"
    | "members"
    | "profile"
    | "feed"
    | "leaderboards"
    | "achievements"
    | "quests"
    | "events"
    | "proposals"
    | "proposal";
}) {
  const t = useT();
  const { memberId } = useParams();
  if (view === "profile" && memberId) return <ProfilePage />;
  if (view === "proposal") return <ProposalDetail />;
  return (
    <div className="ds-stack community-page">
      <PageHeader icon="users" title={t("community:title")} context={t("community:intro")} />
      <nav aria-label={t("community:title")} className="community-tabs">
        {TABS.map((tab) => (
          <NavLink key={tab.key} to={tab.to} end={tab.end}>
            <Icon name={tab.icon} size={16} />
            <span>{t(`community:nav.${tab.key}`)}</span>
          </NavLink>
        ))}
      </nav>
      {view === "discover" ? <CommunityOverview /> : null}
      {view === "members" ? <Directory /> : null}
      {view === "feed" ? <Feed /> : null}
      {view === "leaderboards" ? <LeaderboardPage /> : null}
      {view === "achievements" ? <Showcase /> : null}
      {view === "quests" ? <QuestBoard /> : null}
      {view === "events" ? <EventList /> : null}
      {view === "proposals" ? <ProposalList /> : null}
    </div>
  );
}
