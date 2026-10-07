import { Link, useParams } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { PageHeader } from "../../design-system/components/PageHeader";
import { EmptyState, Skeleton } from "../../design-system/components/Placeholders";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { useActiveCampaigns, useCampaign } from "./api";
import { WindowProgress } from "./WindowProgress";
import "./campaigns.css";

const VALUE_ICONS: Record<string, string> = { xp: "sparkles", coins: "coins", contribution: "heart" };

/** ``/campaigns`` and ``/campaigns/:key`` (spec 014; 027 redesign): what runs now, each campaign as a card —
 * its pitch, how long it lasts, its boosts and the next windows. */
export default function CampaignsPage() {
  const { key } = useParams();
  return key ? <CampaignDetail campaignKey={key} /> : <ActiveList />;
}

function Countdown({ endsAt }: { endsAt: string }) {
  const t = useT();
  const format = useFormat();
  const seconds = (Date.parse(endsAt) - Date.now()) / 1000;
  return (
    <span className="campaign-card__ends">
      <Icon name="hourglass" size={14} />
      {seconds > 0
        ? t("campaigns:page.endsIn", { when: format.relative(seconds) })
        : t("campaigns:page.ended")}
    </span>
  );
}

function CampaignCard({
  campaignKey,
  endsAt,
  full,
}: {
  campaignKey: string;
  endsAt?: string | null;
  full?: boolean;
}) {
  const t = useT();
  const format = useFormat();
  const campaign = useCampaign(campaignKey);
  if (campaign.isPending) return <Skeleton shape="tile" count={1} label={campaignKey} />;
  if (!campaign.data) return null;
  const view = campaign.data;
  const live = view.windows.some(
    (w) => Date.parse(w.start_at) <= Date.now() && Date.parse(w.end_at) > Date.now(),
  );
  const until = endsAt ?? view.windows.find((w) => Date.parse(w.end_at) > Date.now())?.end_at;
  const current = view.windows.find(
    (w) => Date.parse(w.start_at) <= Date.now() && Date.parse(w.end_at) > Date.now(),
  );
  return (
    <article className="campaign-card" data-live={live || undefined}>
      <div className="campaign-card__main">
        <header className="campaign-card__head">
          <span className="campaign-card__icon" aria-hidden="true">
            <Icon name="star" size={22} />
          </span>
          <div className="campaign-card__title">
            {live ? <span className="campaign-card__live">{t("campaigns:page.live")}</span> : null}
            <h2>{full ? view.name : <Link to={`/campaigns/${view.key}`}>{view.name}</Link>}</h2>
          </div>
        </header>
        {view.description ? <p className="campaign-card__pitch">{view.description}</p> : null}
        {view.modifiers.length ? (
          <ul className="campaign-boosts" aria-label={t("campaigns:page.boosts")}>
            {view.modifiers.map((m) => (
              <li key={`${m.value}-${m.factor}`} data-value={m.value}>
                <Icon name={VALUE_ICONS[m.value] ?? "zap"} size={16} />
                <strong>×{m.factor}</strong>
                <span>{t(`gamification:value.${m.value}`)}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      <aside className="campaign-card__side">
        {until ? <Countdown endsAt={until} /> : null}
        {current ? <WindowProgress start={current.start_at} end={current.end_at} /> : null}
        {view.windows.length ? (
          <section className="campaign-windows" aria-label={t("campaigns:page.windows")}>
            <h3>{t("campaigns:page.windows")}</h3>
            <ol>
              {view.windows.slice(0, full ? 5 : 3).map((w) => {
                const leaf = format.dayMonth(w.start_at);
                return (
                  <li key={w.start_at}>
                    <span className="campaign-windows__leaf" aria-hidden="true">
                      <strong>{leaf.day}</strong>
                      <span>{leaf.month}</span>
                    </span>
                    <span>
                      {format.dateTime(w.start_at)} – {format.dateTime(w.end_at)}
                    </span>
                  </li>
                );
              })}
            </ol>
          </section>
        ) : null}
      </aside>
    </article>
  );
}

function ActiveList() {
  const t = useT();
  const active = useActiveCampaigns();
  return (
    <div className="ds-stack">
      <PageHeader icon="star" title={t("campaigns:page.title")} context={t("campaigns:page.intro")} />
      {active.isPending ? <Skeleton shape="tile" count={2} label={t("campaigns:page.title")} /> : null}
      {active.data?.length === 0 ? (
        <EmptyState
          icon="star"
          title={t("campaigns:page.empty")}
          action={
            <Link className="ds-button ds-button--secondary" to="/community">
              {t("campaigns:page.toCommunity")}
            </Link>
          }
        />
      ) : null}
      <div className="campaign-list">
        {(active.data ?? []).map((c) => (
          <CampaignCard key={c.key} campaignKey={c.key} endsAt={c.ends_at} />
        ))}
      </div>
    </div>
  );
}

function CampaignDetail({ campaignKey }: { campaignKey: string }) {
  const t = useT();
  return (
    <div className="ds-stack">
      <Link to="/campaigns" className="campaign-back">
        <Icon name="chevron-left" size={16} />
        {t("campaigns:page.title")}
      </Link>
      <div className="campaign-list">
        <CampaignCard campaignKey={campaignKey} full />
      </div>
    </div>
  );
}
