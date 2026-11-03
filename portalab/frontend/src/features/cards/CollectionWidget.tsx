import { Link } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { useLocaleContext } from "../../i18n/provider/I18nProvider";
import { WidgetHeaderLink } from "../dashboard/frame/actions";
import { CompactLine } from "../dashboard/widgets/compact";
import { registerWidgetComponent, type WidgetProps } from "../dashboard/widgets/registry";
import { BoosterPack } from "../marketplace/boosters/Boosters";
import { bindingOf, CARD_BOOSTER, useSceneBindings } from "../marketplace/boosters/scene/scene";
import type { CardPack, CardsSummary } from "./api";
import { piles } from "./CardBoosters";
import { packBooster, packName } from "./packBooster";
import "../marketplace/boosters/boosters.css";
import "./collection-widget.css";

const BOOSTERS = "/cards?vue=boosters";

/**
 * Dashboard widget ``cards.collection`` (issue 347): « My Mediacards » — where my collection stands, as on
 * ``/cards`` (the cards I have of all there are, the sets started, the copies), and my boosters to open,
 * sealed and stacked as on its « To open » view, which they lead to. On a single row, or in a low block,
 * the figures only. Nothing for a member who does not collect the cards (the server says so).
 */
function CollectionWidget({ payload, compact }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const { locale } = useLocaleContext();
  const bindings = useSceneBindings();
  const data = (payload.data ?? {}) as Partial<CardsSummary> & { packs?: CardPack[] };
  const mine: CardsSummary = {
    unique: 0,
    copies: 0,
    sets_started: 0,
    cards: 0,
    sets: 0,
    unopened: 0,
    ...data,
  };
  const share = mine.cards ? Math.round((mine.unique / mine.cards) * 100) : 0;
  const cards = `${format.number(mine.unique)} / ${format.number(mine.cards)} ${t("gamification:cards.stats.cards")}`;
  const sets = `${format.number(mine.sets_started)} / ${format.number(mine.sets)} ${t("gamification:cards.stats.sets")}`;
  const toOpen = mine.unopened ? t("gamification:cards.packs", { count: mine.unopened }) : null;
  const open = <WidgetHeaderLink to="/cards" label={t("gamification:cards.toCollection")} />;
  if (compact)
    return (
      <>
        {open}
        <CompactLine
          to={mine.unopened ? BOOSTERS : "/cards"}
          icon={mine.unopened ? "gift" : "layers"}
          title={cards}
          detail={toOpen ?? sets}
          end={`${format.number(share)} %`}
        />
      </>
    );
  return (
    <>
      {open}
      <div className="mediacards-widget">
        <section className="mediacards-widget__summary" aria-label={t("gamification:cards.summary")}>
          <div className="mediacards-widget__main">
            <span>
              <strong>{format.number(mine.unique)}</strong> / {format.number(mine.cards)}{" "}
              {t("gamification:cards.stats.cards")}
            </span>
            <span className="mediacards-widget__share">{format.number(share)} %</span>
          </div>
          <span className="mediacards-widget__meter" aria-hidden="true">
            <span style={{ inlineSize: `${share}%` }} />
          </span>
          <div className="mediacards-widget__stats">
            <span>
              <strong>{format.number(mine.sets_started)}</strong> / {format.number(mine.sets)}{" "}
              {t("gamification:cards.stats.sets")}
            </span>
            <span>
              <strong>{format.number(mine.copies)}</strong> {t("gamification:cards.stats.copies")}
            </span>
          </div>
        </section>
        {toOpen ? (
          <section className="mediacards-widget__packs" aria-label={toOpen}>
            <Link className="mediacards-widget__to-open" to={BOOSTERS}>
              <Icon name="gift" size={14} />
              {toOpen}
              <Icon name="chevron-right" size={12} />
            </Link>
            {/* issue 297: the same boosters in one pile, how many on its badge */}
            <ul className="mediacards-widget__piles">
              {piles(data.packs ?? []).map((pile) => {
                const pack = pile[0] as CardPack;
                return (
                  <li key={pack.id}>
                    <Link
                      to={BOOSTERS}
                      className="mediacards-widget__pack"
                      data-booster-look={
                        bindingOf(bindings, pack.look?.product ?? "", CARD_BOOSTER)?.booster_look ?? undefined
                      }
                      data-pile={pile.length > 1 || undefined}
                      aria-label={`${packName(t, pack)}${
                        pile.length > 1
                          ? ` (${t("gamification:cards.pack.pile", { count: pile.length })})`
                          : ""
                      }`}
                    >
                      <BoosterPack booster={packBooster(t, pack, locale)} size="card" />
                      {pile.length > 1 ? (
                        <span className="mediacards-widget__pile" aria-hidden="true">
                          <Icon name="layers" size={12} />
                          {pile.length}
                        </span>
                      ) : null}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </section>
        ) : null}
      </div>
    </>
  );
}

registerWidgetComponent("cards.collection", CollectionWidget);
