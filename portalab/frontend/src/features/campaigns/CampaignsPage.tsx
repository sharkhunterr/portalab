import { Link, useParams } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { PageHeader } from "../../design-system/components/PageHeader";
import { EmptyState, Skeleton } from "../../design-system/components/Placeholders";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { type CampaignView, discountScope, useActiveCampaigns, useCampaign } from "./api";
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
        <Brings view={view} />
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

/** 027: what the campaign brings, in words — each boost and what it applies to, the shop reductions, its
 * own achievements and quests. */
function Brings({ view }: { view: CampaignView }) {
  const t = useT();
  const discounts = view.discounts ?? [];
  const achievements = view.achievements ?? [];
  const quests = view.quests ?? [];
  if (!view.modifiers.length && !discounts.length && !achievements.length && !quests.length) return null;
  const kinds = (list: string[] = []) => list.map((k) => t(`media:kind.${k}`)).join(", ");
  // what the member does, in words (« finish a film or an episode »), never the event's technical name
  const activities = (list: string[]) => {
    const words = list
      .map((event) => {
        const key = `page.activity.${event}`;
        const text = t(`campaigns:${key}`);
        return text === key ? null : text;
      })
      .filter(Boolean);
    return words.length ? words.join(", ") : t("campaigns:page.activity.other");
  };
  return (
    <section className="campaign-brings" aria-label={t("campaigns:page.brings")}>
      <h3>{t("campaigns:page.brings")}</h3>
      <ul>
        {view.modifiers.map((m, index) => {
          const scope = [
            m.kinds?.length ? t("campaigns:page.on.kinds", { kinds: kinds(m.kinds) }) : null,
            m.genres?.length ? t("campaigns:page.on.genres", { genres: m.genres.join(", ") }) : null,
            m.activities?.length
              ? t("campaigns:page.on.activities", { activities: activities(m.activities) })
              : null,
            m.titles?.length ? t("campaigns:page.on.titles", { titles: m.titles.join(", ") }) : null,
          ].filter(Boolean);
          return (
            // biome-ignore lint/suspicious/noArrayIndexKey: a campaign may boost the same value twice
            <li key={`${m.value}-${index}`} data-value={m.value}>
              <span className="campaign-brings__badge">
                <Icon name={VALUE_ICONS[m.value] ?? "zap"} size={16} />
                <strong>×{m.factor}</strong> {t(`gamification:value.${m.value}`)}
              </span>
              <span className="campaign-brings__what">
                {scope.length ? scope.join(" · ") : t("campaigns:page.on.everything")}
                {m.everyone === false ? ` · ${t("campaigns:page.on.some")}` : ""}
              </span>
            </li>
          );
        })}
        {discounts.map((d, index) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: reductions in order
          <li key={`discount-${index}`} data-value="discount">
            <span className="campaign-brings__badge">
              <Icon name="shop" size={16} />
              <strong>−{d.percent} %</strong>
            </span>
            <span className="campaign-brings__what">
              {t("campaigns:page.discountOn", { what: discountScope(t, d) })}{" "}
              <Link to="/marketplace">{t("campaigns:page.toShop")}</Link>
            </span>
          </li>
        ))}
        {achievements.length ? (
          <li data-value="achievements">
            <span className="campaign-brings__badge">
              <Icon name="trophy" size={16} />
              <strong>{achievements.length}</strong>
            </span>
            <span className="campaign-brings__what">
              {t("campaigns:page.achievements", { count: achievements.length })} :{" "}
              {achievements.map((a) => a.label).join(", ")}
            </span>
          </li>
        ) : null}
        {quests.length ? (
          <li data-value="quests">
            <span className="campaign-brings__badge">
              <Icon name="target" size={16} />
              <strong>{quests.length}</strong>
            </span>
            <span className="campaign-brings__what">
              {t("campaigns:page.quests", { count: quests.length })} : {quests.map((q) => q.label).join(", ")}
            </span>
          </li>
        ) : null}
      </ul>
    </section>
  );
}

/** #298: the campaigns running now among the community's events — nothing when none runs. */
export function RunningCampaigns() {
  const t = useT();
  const active = useActiveCampaigns();
  if (!active.data?.length) return null;
  return (
    <section className="ds-stack" aria-label={t("campaigns:page.title")}>
      <h2>{t("campaigns:page.title")}</h2>
      <div className="campaign-list">
        {active.data.map((c) => (
          <CampaignCard key={c.key} campaignKey={c.key} endsAt={c.ends_at} />
        ))}
      </div>
    </section>
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
