import { Link } from "react-router";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useActiveCampaigns } from "../api";

/** Active-campaign banner (spec 014 T024): only the campaigns that concern me; silent otherwise. */
export function ActiveCampaignBanner() {
  const t = useT();
  const format = useFormat();
  const active = useActiveCampaigns();
  if (!active.data?.length) return null;
  return (
    <aside className="ds-card campaign-banner" aria-label={t("campaigns:banner.label")}>
      <ul>
        {active.data.map((campaign) => (
          <li key={campaign.key}>
            <strong>{t("campaigns:banner.label")}</strong> ·{" "}
            <Link to={`/campaigns/${campaign.key}`}>{campaign.name}</Link>
            {campaign.ends_at ? (
              <> · {t("campaigns:banner.ends", { date: format.dateTime(campaign.ends_at) })}</>
            ) : null}
          </li>
        ))}
      </ul>
    </aside>
  );
}
