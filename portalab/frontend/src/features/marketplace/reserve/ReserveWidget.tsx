import { Link } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { usePacks } from "../../cards/api";
import { useCollectsCards } from "../../cards/collects";
import { WidgetHeaderAction, WidgetHeaderLink } from "../../dashboard/frame/actions";
import { CompactLine } from "../../dashboard/widgets/compact";
import { registerWidgetComponent, type WidgetProps } from "../../dashboard/widgets/registry";
import { TYPE_ICONS } from "../catalog/ProductPoster";
import "../marketplace.css";
import "./reserve-widget.css";

type Section = "todo" | "open" | "use" | "waiting";

interface ReserveTile {
  key: string;
  name: string;
  type: string;
  rarity?: string | null;
  icon?: string | null;
  quantity: number;
  section: Section;
  new?: boolean;
}

/** The reserve page's sections, in its order (ReservePage). */
const SECTIONS: ReadonlyArray<{ key: Section; icon: string }> = [
  { key: "todo", icon: "sparkles" },
  { key: "open", icon: "gift" },
  { key: "use", icon: "zap" },
  { key: "waiting", icon: "lock" },
];
const PAGE = "/marketplace/reserve";

/**
 * Dashboard widget ``marketplace.reserve`` (issue 347): what waits in my reserve — how many of each of its
 * page's sections (my card boosters among those to open, as on the page), the first things as tiles
 * (identical ones stacked, how many on them), and what came in since I last opened it (issue 300). On a
 * single row, or in a low block, the counts only.
 */
function ReserveWidget({ payload, compact }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const data = (payload.data ?? {}) as {
    counts?: Partial<Record<Section, number>>;
    new?: number;
    items?: ReserveTile[];
  };
  const collects = useCollectsCards(); // issue 243: not for a member who plays without the cards
  const packs = usePacks(collects).data ?? [];
  const counts: Record<Section, number> = { todo: 0, open: 0, use: 0, waiting: 0, ...data.counts };
  counts.open += collects ? packs.length : 0;
  const shown = SECTIONS.filter((section) => counts[section.key] > 0);
  const fresh = data.new ?? 0;
  const items = data.items ?? [];
  const header = (
    <>
      {fresh ? (
        <WidgetHeaderAction>
          <span className="widget-unread">
            <span className="widget-unread__dot" aria-hidden="true" />
            {t("marketplace:widget.reserve.new", { count: fresh })}
          </span>
        </WidgetHeaderAction>
      ) : null}
      <WidgetHeaderLink to={PAGE} label={t("marketplace:widget.reserve.open")} />
    </>
  );
  if (compact)
    return (
      <>
        {header}
        <CompactLine
          to={PAGE}
          icon="potion"
          title={
            shown.length
              ? shown
                  .map((section) =>
                    t(`marketplace:widget.reserve.count.${section.key}`, { count: counts[section.key] }),
                  )
                  .join(" · ")
              : t("marketplace:reserve.empty")
          }
        />
      </>
    );
  return (
    <>
      {header}
      <div className="reserve-widget">
        <ul
          className="reserve-widget__counts"
          aria-label={t("marketplace:widget.reserve.sections")}
          data-nofit
        >
          {shown.map((section) => (
            <li key={section.key}>
              <Link
                to={PAGE}
                className="reserve-widget__section"
                data-tone={section.key === "todo" ? "todo" : undefined}
              >
                <Icon name={section.icon} size={16} />
                <strong>{format.number(counts[section.key])}</strong>
                <span>{t(`marketplace:reserve.section.${section.key}`)}</span>
              </Link>
            </li>
          ))}
        </ul>
        {items.length ? (
          <ul className="reserve-widget__tiles">
            {items.map((item) => (
              <li
                key={`${item.section}:${item.key}`}
                className="reserve-widget__tile"
                data-rarity={item.rarity ?? "common"}
                data-tone={
                  item.section === "todo" ? "todo" : item.section === "waiting" ? "locked" : undefined
                }
              >
                <Link to={PAGE} className="reserve-widget__link" title={item.name}>
                  <span className="reserve-widget__art" aria-hidden="true">
                    <Icon name={item.icon ?? TYPE_ICONS[item.type] ?? "potion"} size={22} />
                    {item.quantity > 1 ? (
                      <span className="reserve-widget__count">
                        {t("marketplace:reserve.quantity", { count: item.quantity })}
                      </span>
                    ) : null}
                    {item.section === "waiting" ? (
                      <span className="reserve-widget__lock">
                        <Icon name="lock" size={11} />
                      </span>
                    ) : null}
                  </span>
                  <span className="reserve-widget__name">
                    {item.new ? <span className="widget-unread__dot" aria-hidden="true" /> : null}
                    {item.name}
                  </span>
                  {item.quantity > 1 ? (
                    <span className="visually-hidden">
                      {t("marketplace:reserve.quantity", { count: item.quantity })}
                    </span>
                  ) : null}
                  {item.new ? (
                    <span className="visually-hidden">{t("marketplace:widget.reserve.newItem")}</span>
                  ) : null}
                </Link>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </>
  );
}

registerWidgetComponent("marketplace.reserve", ReserveWidget);
