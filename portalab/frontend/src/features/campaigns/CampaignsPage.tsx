import { Link, useParams } from "react-router";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { useActiveCampaigns, useCampaign } from "./api";
import { ActiveCampaignBanner } from "./banner/ActiveCampaignBanner";
import "./campaigns.css";

/** ``/campaigns`` and ``/campaigns/:key`` (spec 014): what runs now and a campaign's public view. */
export default function CampaignsPage() {
  const { key } = useParams();
  return key ? <CampaignDetail campaignKey={key} /> : <ActiveList />;
}

function ActiveList() {
  const t = useT();
  const active = useActiveCampaigns();
  return (
    <div className="ds-stack">
      <h1>{t("campaigns:page.title")}</h1>
      <ActiveCampaignBanner />
      {active.data?.length === 0 ? <p>{t("campaigns:page.empty")}</p> : null}
      <ul>
        {(active.data ?? []).map((c) => (
          <li key={c.key}>
            <Link to={`/campaigns/${c.key}`}>{c.name}</Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CampaignDetail({ campaignKey }: { campaignKey: string }) {
  const t = useT();
  const format = useFormat();
  const campaign = useCampaign(campaignKey);
  if (!campaign.data) return null;
  const view = campaign.data;
  return (
    <article className="ds-stack">
      <h1>{view.name}</h1>
      {view.description ? <p>{view.description}</p> : null}
      <h2>{t("campaigns:page.windows")}</h2>
      <ul>
        {view.windows.map((w) => (
          <li key={w.start_at}>
            {format.dateTime(w.start_at)} – {format.dateTime(w.end_at)}
          </li>
        ))}
      </ul>
      {view.modifiers.length ? (
        <>
          <h2>{t("campaigns:page.boosts")}</h2>
          <ul>
            {view.modifiers.map((m, index) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: modifiers have no public id
              <li key={index}>
                {t("campaigns:boost", { value: t(`gamification:value.${m.value}`), factor: m.factor })}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </article>
  );
}
