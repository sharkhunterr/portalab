import { NavLink, useParams } from "react-router";
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

const TABS = [
  { to: "/community", key: "discover", end: true },
  { to: "/community/members", key: "members", end: true },
  { to: "/community/feed", key: "feed", end: true },
  { to: "/community/proposals", key: "proposals", end: false },
  { to: "/community/leaderboards", key: "leaderboards", end: true },
  { to: "/community/achievements", key: "achievements", end: true },
  { to: "/community/events", key: "events", end: true },
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
    <div className="ds-stack">
      <h1>{t("community:title")}</h1>
      <p>{t("community:intro")}</p>
      <nav aria-label={t("community:title")} className="community-tabs">
        {TABS.map((tab) => (
          <NavLink key={tab.key} to={tab.to} end={tab.end}>
            {t(`community:nav.${tab.key}`)}
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
