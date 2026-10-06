import { Link } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { registerWidgetComponent, type WidgetProps } from "../dashboard/widgets/registry";
import "./campaigns.css";

interface Item {
  key: string;
  title: string;
  route: string;
  ends_at: string | null;
  description: string;
  boosts: Array<{ value: string; factor: number }>;
}

const VALUE_ICONS: Record<string, string> = { xp: "sparkles", coins: "coins", contribution: "heart" };

/** Dashboard widget ``campaigns.active`` (027 redesign): each running campaign as a small card — its
 * boosts in big, how long is left. */
function CampaignsWidget({ payload }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const items = ((payload.data ?? {}) as { items?: Item[] }).items ?? [];
  return (
    <ul className="campaigns-widget">
      {items.map((item) => {
        const left = item.ends_at ? (Date.parse(item.ends_at) - Date.now()) / 1000 : null;
        return (
          <li key={item.key}>
            <Link to={item.route} className="campaigns-widget__card">
              <span className="campaigns-widget__head">
                <span className="campaigns-widget__icon" aria-hidden="true">
                  <Icon name="star" size={16} />
                </span>
                <strong>{item.title}</strong>
                {left !== null ? (
                  <span className="campaigns-widget__left">
                    <Icon name="hourglass" size={12} />
                    {left > 0 ? format.relative(left) : t("campaigns:page.ended")}
                  </span>
                ) : null}
              </span>
              {item.boosts.length ? (
                <span className="campaigns-widget__boosts">
                  {item.boosts.map((boost) => (
                    <span key={`${boost.value}-${boost.factor}`}>
                      <Icon name={VALUE_ICONS[boost.value] ?? "zap"} size={14} />
                      <strong>×{boost.factor}</strong> {t(`gamification:value.${boost.value}`)}
                    </span>
                  ))}
                </span>
              ) : null}
              {item.description ? <span className="campaigns-widget__pitch">{item.description}</span> : null}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

registerWidgetComponent("campaigns.active", CampaignsWidget);
