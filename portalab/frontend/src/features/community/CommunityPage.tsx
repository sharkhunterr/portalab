import { NavLink, useParams } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { QuestBoard } from "./achievements/QuestBoard";
import { Showcase } from "./achievements/Showcase";
import { DiscoveryHome } from "./discovery/DiscoveryHome";
import { EventList } from "./events/EventList";
import { Feed } from "./feed/Feed";
import { LeaderboardPage } from "./leaderboards/LeaderboardPage";
import { Directory } from "./members/Directory";
import { ProfilePage } from "./profile/ProfilePage";
import { ProposalDetail } from "./projects/ProposalDetail";
import { ProposalList } from "./projects/ProposalList";
import "./community.css";
import { PageHeader } from "../../design-system/components/PageHeader";

const TABS = [
  { to: "/community", key: "discover", end: true, icon: "compass" },
  { to: "/community/members", key: "members", end: true, icon: "users" },
  { to: "/community/feed", key: "feed", end: true, icon: "activity" },
  { to: "/community/proposals", key: "proposals", end: false, icon: "lightbulb" },
  { to: "/community/leaderboards", key: "leaderboards", end: true, icon: "medal" },
  { to: "/community/achievements", key: "achievements", end: true, icon: "trophy" },
  { to: "/community/events", key: "events", end: true, icon: "calendar" },
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
      {view === "discover" ? <DiscoveryHome /> : null}
      {view === "members" ? <Directory /> : null}
      {view === "feed" ? <Feed /> : null}
      {view === "leaderboards" ? <LeaderboardPage /> : null}
      {view === "achievements" ? (
        <>
          <Showcase />
          <QuestBoard />
        </>
      ) : null}
      {view === "events" ? <EventList /> : null}
      {view === "proposals" ? <ProposalList /> : null}
    </div>
  );
}
