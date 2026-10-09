import { Link } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { CompactLine } from "../dashboard/widgets/compact";
import { registerWidgetComponent, type WidgetProps } from "../dashboard/widgets/registry";
import { WindowProgress } from "./WindowProgress";
import "./campaigns.css";

interface Item {
  key: string;
  title: string;
  route: string;
  starts_at?: string | null;
  ends_at: string | null;
  description: string;
  boosts: Array<{ value: string; factor: number }>;
}

const VALUE_ICONS: Record<string, string> = { xp: "sparkles", coins: "coins", contribution: "heart" };

/** Dashboard widget ``campaigns.active`` (027 redesign): each running campaign as a small card — its
 * boosts in big, how long is left. */
function CampaignsWidget({ payload, compact }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const data = (payload.data ?? {}) as {
    items?: Item[];
    next?: { title: string; starts_at: string | null; route: string } | null;
  };
  const items = data.items ?? [];
  if (!items.length) {
    // 027: nothing running — what comes next (a pinned block is never empty)
    return (
      <div className="campaigns-widget__calm">
        <span className="campaigns-widget__icon" aria-hidden="true">
          <Icon name="star" size={16} />
        </span>
        {data.next ? (
          <Link to={data.next.route}>
            {t("campaigns:widget.next", {
              name: data.next.title,
              when: data.next.starts_at ? format.date(data.next.starts_at, "medium") : "",
            })}
          </Link>
        ) : (
          <span>{t("campaigns:widget.none")}</span>
        )}
      </div>
    );
  }
  const first = items[0];
  if (compact && first) {
    // 027 (#36): the running campaign — what it boosts and how long is left
    const left = first.ends_at ? (Date.parse(first.ends_at) - Date.now()) / 1000 : null;
    return (
      <CompactLine
        to={first.route}
        icon="star"
        title={first.title}
        detail={first.boosts
          .map((boost) => `×${boost.factor} ${t(`gamification:value.${boost.value}`)}`)
          .join(" · ")}
        end={
          left !== null ? (
            <>
              <Icon name="hourglass" size={12} />
              {left > 0 ? format.relative(left) : t("campaigns:page.ended")}
            </>
          ) : null
        }
      />
    );
  }
  return (
    <ul className="campaigns-widget">
      {items.map((item) => {
        const left = item.ends_at ? (Date.parse(item.ends_at) - Date.now()) / 1000 : null;
        return (
          <li key={item.key}>
            <Link to={item.route} className="campaigns-widget__card">
              <span className="campaigns-widget__who">
                <span className="campaigns-widget__icon" aria-hidden="true">
                  <Icon name="star" size={16} />
                </span>
                <span className="campaigns-widget__name">
                  <strong>{item.title}</strong>
                  {item.description ? (
                    <span className="campaigns-widget__pitch">{item.description}</span>
                  ) : null}
                </span>
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
              {left !== null ? (
                <span className="campaigns-widget__time">
                  <span className="campaigns-widget__left">
                    <Icon name="hourglass" size={12} />
                    {left > 0 ? format.relative(left) : t("campaigns:page.ended")}
                  </span>
                  {item.starts_at && item.ends_at ? (
                    <WindowProgress start={item.starts_at} end={item.ends_at} />
                  ) : null}
                </span>
              ) : null}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

registerWidgetComponent("campaigns.active", CampaignsWidget);
