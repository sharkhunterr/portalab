import { useParams } from "react-router";
import { useT } from "../../i18n/hooks/useT";
import { useHasPermission } from "../authz/useMyPermissions";
import { RunningCampaigns } from "../campaigns/CampaignsPage";
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

const ICONS = {
  members: "users",
  profile: "user",
  feed: "activity",
  leaderboards: "medal",
  achievements: "trophy",
  quests: "target",
  events: "calendar",
  proposals: "lightbulb",
} as const;

/** ``/community/*`` (spec 012, slice A): discovery, members, activity and events (with the running campaigns). */
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
  const campaigns = useHasPermission("campaigns.read");
  if (view === "profile" && memberId) return <ProfilePage />;
  if (view === "proposal") return <ProposalDetail />;
  return (
    <div className="ds-stack community-page">
      {/* #298: the pages are the navigation's tabs (a single bar); the overview introduces the community */}
      {view === "discover" ? (
        <PageHeader icon="users" title={t("community:title")} context={t("community:intro")} />
      ) : (
        <PageHeader icon={ICONS[view]} title={t(`community:nav.${view}`)} />
      )}
      {view === "discover" ? <CommunityOverview /> : null}
      {view === "members" ? <Directory /> : null}
      {view === "feed" ? <Feed /> : null}
      {view === "leaderboards" ? <LeaderboardPage /> : null}
      {view === "achievements" ? <Showcase /> : null}
      {view === "quests" ? <QuestBoard /> : null}
      {view === "events" && campaigns ? <RunningCampaigns /> : null}
      {view === "events" ? <EventList /> : null}
      {view === "proposals" ? <ProposalList /> : null}
    </div>
  );
}
