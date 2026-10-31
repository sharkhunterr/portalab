import { lazy, Suspense, useState } from "react";
import { Link } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { useLocaleContext } from "../../i18n/provider/I18nProvider";
import type { Product } from "../marketplace/api";
import type { BoosterCard } from "../marketplace/boosters/api";
import { BoosterPack } from "../marketplace/boosters/Boosters";
import { bindingOf, CARD_BOOSTER, useSceneBindings } from "../marketplace/boosters/scene/scene";
import { type CardPack, type MediaCard, useOpenPack, usePacks } from "./api";
import { MediaCardView } from "./MediaCardView";
import { packBooster, packName } from "./packBooster";
import "../marketplace/boosters/boosters.css";
import "./cardStage.css";

const BoosterReveal = lazy(() =>
  import("../marketplace/boosters/BoosterReveal").then((m) => ({ default: m.BoosterReveal })),
);

/** A drawn card on the booster stage: its own face (the media card), new or already owned. */
function revealed(card: MediaCard): BoosterCard {
  return {
    product: { key: card.copy ?? card.id, name: card.name, rarity: card.rarity, type: "card" } as Product,
    outcome: card.new === false ? "duplicate" : "new",
    duplicate: false, // nothing given back: a second copy is a card to keep
    refund: 0,
    locked: false,
    face: <MediaCardView card={card} variant={card.variant ?? "normal"} />,
  };
}

/** Issue 297: sealed packs that are the same booster (the same product, or the same content and season) — one
 * pile each, in the order the first of each came. */
export function piles(packs: CardPack[]): CardPack[][] {
  const out = new Map<string, CardPack[]>();
  for (const pack of packs) {
    const look = pack.look;
    const key = [pack.source, look?.product ?? pack.set ?? "", look?.season ?? ""].join("|");
    out.set(key, [...(out.get(key) ?? []), pack]);
  }
  return [...out.values()];
}

/** Issue 234: my sealed card boosters (a film watched, a season finished, one bought) — in my inventory and on
 * my cards' page, each as the shop's sealed boosters are; opened on the same stage. */
export function CardBoosters({ inventory = false }: { inventory?: boolean }) {
  const t = useT();
  const { locale } = useLocaleContext();
  const packs = usePacks().data ?? [];
  const open = useOpenPack();
  // issue 243: the Mediacards boosters' own wrapper (the scene bound to their kind), apart from the looks' —
  // issue 293: a bought one's, the scene bound to its product, as in the shop
  const bindings = useSceneBindings();
  const lookOf = (pack: CardPack) =>
    bindingOf(bindings, pack.look?.product ?? "", CARD_BOOSTER)?.booster_look ?? undefined;
  // kept while it is opened: the list loses it as soon as it is
  const [opening, setOpening] = useState<CardPack | null>(null);
  return (
    <>
      {packs.length ? (
        <section className="cards-packs" aria-labelledby="cards-packs">
          <h2 id="cards-packs">
            <Icon name="gift" size={18} /> {t("gamification:cards.packs", { count: packs.length })}
            {inventory ? <Link to="/cards">{t("gamification:cards.toCollection")}</Link> : null}
          </h2>
          <ul className="cards-boosters">
            {/* issue 297: the same boosters in one pile, how many on its badge — a tap opens the first */}
            {piles(packs).map((pile) => {
              const pack = pile[0] as CardPack;
              return (
                <li key={pack.id}>
                  <button
                    type="button"
                    className="cards-boosters__pack"
                    data-booster-look={lookOf(pack)}
                    data-pile={pile.length > 1 || undefined}
                    onClick={() => setOpening(pack)}
                    aria-label={`${t("gamification:cards.pack.open")} — ${packName(t, pack)}${
                      pile.length > 1 ? ` (${t("gamification:cards.pack.pile", { count: pile.length })})` : ""
                    }`}
                  >
                    <BoosterPack booster={packBooster(t, pack, locale)} />
                    {pile.length > 1 ? (
                      <span className="cards-boosters__pile" aria-hidden="true">
                        <Icon name="layers" size={14} />
                        {pile.length}
                      </span>
                    ) : null}
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}
      {opening ? (
        <Suspense fallback={null}>
          <BoosterReveal
            booster={packBooster(t, opening, locale)}
            sceneKind={CARD_BOOSTER}
            sealed
            onClose={() => setOpening(null)}
            opener={{
              open: async () => {
                const opened = await open.mutateAsync(opening.id);
                const order = { common: 0, rare: 1, epic: 2, legendary: 3 } as const;
                // the rarest last, as a pack is turned
                return [...opened.cards].sort((a, b) => order[a.rarity] - order[b.rarity]).map(revealed);
              },
              link: { to: "/cards", label: t("gamification:cards.toCollection") },
              fresh: (count) => t("gamification:cards.pack.fresh", { count }),
            }}
          />
        </Suspense>
      ) : null}
    </>
  );
}
