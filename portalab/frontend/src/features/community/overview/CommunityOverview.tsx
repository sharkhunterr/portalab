import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { Avatar } from "../../../design-system/components/Avatar";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useActiveCampaigns } from "../../campaigns/api";
import { Leaderboard } from "../../gamification/leaderboards/Leaderboard";
import type { QuestItem } from "../../gamification/quests/QuestList";
import { useFeed } from "../api";
import { DiscoveryHome } from "../discovery/DiscoveryHome";
import { FEED_ICONS, FeedText } from "../feed/FeedText";
import { Podium } from "../leaderboards/LeaderboardPage";

function Panel({
  icon,
  title,
  more,
  children,
  wide,
}: {
  icon: string;
  title: string;
  more?: string | undefined;
  children: ReactNode;
  wide?: boolean;
}) {
  const t = useT();
  return (
    <section className="community-panel" data-wide={wide || undefined} aria-label={title}>
      <header className="community-panel__head">
        <h3>
          <span className="community-panel__icon" aria-hidden="true">
            <Icon name={icon} size={16} />
          </span>
          {title}
        </h3>
        {more ? (
          <Link to={more} className="community-panel__more">
            {t("community:discovery.more")}
            <Icon name="chevron-right" size={14} />
          </Link>
        ) : null}
      </header>
      {children}
    </section>
  );
}

/** The XP leaderboard's podium and my own place. */
function TopPanel() {
  const t = useT();
  const format = useFormat();
  const board = useQuery({
    queryKey: ["community", "leaderboard", "xp", "month"],
    queryFn: async () =>
      (
        await api.GET("/api/v1/community/leaderboards/{metric}", {
          params: { path: { metric: "xp" }, query: { period: "month" } },
        })
      ).data,
  });
  const data = board.data;
  return (
    <Panel icon="medal" title={t("community:overview.leaderboard")} more="/community/leaderboards" wide>
      {board.isError || data?.state === "unavailable" ? (
        <FunctionalState state="unavailable" label={t("community:leaderboards.unavailable")} />
      ) : null}
      {data && data.state !== "unavailable" ? (
        data.entries.length ? (
          <>
            <Podium rows={data.entries} />
            {data.entries.some((row) => row.rank > 3) ? (
              // #66: the others under the podium, with their moves since a day
              <Leaderboard
                caption={t("community:overview.leaderboard")}
                rows={data.entries.filter((row) => row.rank > 3 && row.rank <= 10)}
                me={data.me}
                profileLinks
              />
            ) : data.me && data.me.rank > 3 ? (
              <p className="community-overview__me">
                {t("community:overview.myRank", { rank: data.me.rank, score: format.number(data.me.score) })}
              </p>
            ) : null}
          </>
        ) : (
          <p className="community-panel__empty">{t("community:overview.noRank")}</p>
        )
      ) : null}
    </Panel>
  );
}

/** My open quests, the closest to done first. */
function QuestsPanel() {
  const t = useT();
  const format = useFormat();
  const quests = useQuery({
    queryKey: ["community", "quests"],
    queryFn: async () => (await api.GET("/api/v1/community/quests")).data,
  });
  const items = ((quests.data?.items ?? []) as unknown as QuestItem[]).filter((q) => !q.completed);
  const ratio = (q: QuestItem) => {
    const step = q.steps[0];
    return step ? Math.min(1, step.current / Math.max(1, step.target)) : 0;
  };
  const shown = [...items].sort((a, b) => ratio(b) - ratio(a)).slice(0, 4);
  return (
    <Panel icon="target" title={t("community:overview.quests")} more="/community/quests">
      {quests.isError || quests.data?.state === "unavailable" ? (
        <FunctionalState state="unavailable" label={t("community:progress.unavailable")} />
      ) : null}
      {quests.data && !shown.length ? (
        <p className="community-panel__empty">{t("community:overview.questsDone")}</p>
      ) : null}
      <ul className="community-quests">
        {shown.map((quest) => {
          const step = quest.steps[0];
          return (
            <li key={quest.key}>
              <span className="community-quests__label">{quest.label}</span>
              <span className="community-quests__bar" aria-hidden="true">
                <span style={{ inlineSize: `${Math.round(ratio(quest) * 100)}%` }} />
              </span>
              <small>
                {step ? `${format.number(step.current)} / ${format.number(step.target)}` : null}
                {quest.rewards.map(
                  (r) => ` · +${format.number(r.amount)} ${t(`gamification:value.${r.value}`)}`,
                )}
              </small>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}

/** The campaigns running now: what they boost and until when. */
function CampaignsPanel() {
  const t = useT();
  const format = useFormat();
  const active = useActiveCampaigns().data;
  const campaigns = Array.isArray(active) ? active : [];
  return (
    <Panel icon="star" title={t("community:overview.campaigns")} more="/campaigns">
      {campaigns.length ? (
        <ul className="community-campaigns">
          {campaigns.map((campaign) => (
            <li key={campaign.key}>
              <Link to={`/campaigns/${campaign.key}`}>
                <strong>{campaign.name}</strong>
                {(campaign.boosts ?? []).map((boost) => (
                  <span key={boost.value} className="community-campaigns__boost">
                    ×{Number(boost.factor.toFixed(2))} {t(`gamification:value.${boost.value}`)}
                  </span>
                ))}
              </Link>
              {campaign.ends_at ? (
                <small>{t("community:overview.until", { date: format.date(campaign.ends_at) })}</small>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="community-panel__empty">{t("community:overview.noCampaign")}</p>
      )}
    </Panel>
  );
}

/** The latest activity of the members I may see. */
function ActivityPanel() {
  const t = useT();
  const format = useFormat();
  const feed = useFeed();
  const items = (feed.data?.pages.flatMap((page) => page.items) ?? []).slice(0, 8);
  return (
    <Panel icon="activity" title={t("community:overview.activity")} more="/community/feed" wide>
      {feed.isError ? <FunctionalState state="unavailable" onRetry={() => feed.refetch()} /> : null}
      {feed.isSuccess && !items.length ? (
        <p className="community-panel__empty">{t("community:feed.empty")}</p>
      ) : null}
      <ol className="community-overview__feed">
        {items.map((item) => (
          <li key={item.id}>
            <Avatar
              name={item.actor_name ?? ""}
              userId={item.actor_id}
              src={`/api/v1/users/${item.actor_id}/avatar`}
              size="sm"
              decorative
            />
            <span className="community-shelf__icon" aria-hidden="true">
              <Icon name={FEED_ICONS[item.kind] ?? "activity"} size={14} />
            </span>
            <span className="community-overview__text">
              <FeedText
                kind={item.kind}
                actorId={item.actor_id}
                actorName={item.actor_name}
                params={item.params ?? {}}
              />
            </span>
            <small>{format.relative((new Date(item.occurred_at).getTime() - Date.now()) / 1000)}</small>
          </li>
        ))}
      </ol>
    </Panel>
  );
}

/**
 * ``/community`` (#63): what the community does now, at a glance — the leaderboard's podium and my place,
 * my quests, the campaigns running and the latest activity; the discovery shelves (new faces, projects to
 * support, recent achievements) follow.
 */
export function CommunityOverview() {
  return (
    <div className="ds-stack">
      <div className="community-overview">
        <TopPanel />
        <QuestsPanel />
        <ActivityPanel />
        <CampaignsPanel />
      </div>
      <DiscoveryHome without={["activity_highlights"]} />
    </div>
  );
}
