import { Link, useParams, useSearchParams } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { Dialog } from "../../design-system/components/Overlays";
import { PageHeader } from "../../design-system/components/PageHeader";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { externalLooks } from "../../design-system/visuals/registry";
import { useT } from "../../i18n/hooks/useT";
import { useLocaleContext } from "../../i18n/provider/I18nProvider";
import { type MediaCard, useCardPerson, useCardSet, VARIANTS, type Variant, variantParts } from "./api";
import { CardCredit } from "./CardCredit";
import { MediaCardView } from "./MediaCardView";
import "./cards.css";

/** Issue 296: the booster signature frames a card is owned in (their foil first). */
function signed(card: MediaCard): Variant[] {
  return (Object.keys(card.owned) as Variant[])
    .filter((v) => v.startsWith("signature") && (card.owned[v] ?? 0) > 0)
    .sort((a, b) => b.localeCompare(a));
}

/** The best version owned of a card (the one shown in the binder): its HD, a booster's signature frame, then
 * the rarest of the others. */
export function best(card: MediaCard): Variant | null {
  if ((card.owned.hd ?? 0) > 0) return "hd";
  return signed(card)[0] ?? [...VARIANTS].reverse().find((v) => (card.owned[v] ?? 0) > 0) ?? null;
}

/** Issue 296: a signature frame's name — its scene's, else its look's. */
function useFrameName(): (look: string) => string {
  const { locale } = useLocaleContext();
  return (look) => {
    const scene = externalLooks("booster_scene").find((e) => e.look === look);
    const named = scene?.names?.[locale.slice(0, 2)] ?? scene?.names?.en;
    // a scene's name says it is one (« Scène Impact »): the frame takes the rest
    return (
      named?.replace(/^(Scène|Scene)\s+/i, "") ??
      look.charAt(0).toUpperCase() + look.slice(1).replace(/-/g, " ")
    );
  };
}

/** A card, big, with every version (the borderless alternative is a work's only): the owned ones in colour,
 * how many of each. */
export function CardSheet({ card }: { card: MediaCard }) {
  const t = useT();
  const frameName = useFrameName();
  const shown = best(card);
  return (
    <Dialog
      size="lg"
      title={card.name}
      closeLabel={t("gamification:cards.close")}
      trigger={
        <button type="button" className="cards-binder__slot" aria-label={card.name}>
          <MediaCardView card={card} variant={shown ?? "normal"} missing={!shown} size="sm" />
          {Object.values(card.owned).reduce<number>((a, b) => a + (b ?? 0), 0) > 1 ? (
            <span className="cards-binder__count">
              ×{Object.values(card.owned).reduce<number>((a, b) => a + (b ?? 0), 0)}
            </span>
          ) : null}
        </button>
      }
    >
      <div className="cards-sheet">
        {[
          ...VARIANTS.filter((v) =>
            v.startsWith("borderless")
              ? card.kind === "title" && card.rarity !== "common"
              : v.startsWith("showcase")
                ? Boolean(card.set_edition)
                : v === "hd"
                  ? card.rarity === "legendary" && Boolean(card.set_edition) // issue 255
                  : true,
          ),
          ...signed(card),
        ].map((variant) => (
          <figure key={variant} data-owned={(card.owned[variant] ?? 0) > 0 || undefined}>
            <MediaCardView card={card} variant={variant} missing={!(card.owned[variant] ?? 0)} />
            <figcaption>
              {t(`gamification:cards.variant.${variantParts(variant).base}`, {
                edition: card.set_edition ? t(`gamification:cards.edition.${card.set_edition}`) : "",
                genre: t(`gamification:cards.genre.${card.set_genre ?? "drama"}`),
                frame: frameName(variantParts(variant).signature ?? ""),
              })}{" "}
              · ×{card.owned[variant] ?? 0}
            </figcaption>
          </figure>
        ))}
      </div>
      {card.person ? (
        <p>
          <Link to={`/cards/people?ref=${encodeURIComponent(card.person)}`}>
            <Icon name="user" size={14} /> {t("gamification:cards.allOf", { name: card.name })}
          </Link>
        </p>
      ) : null}
    </Dialog>
  );
}

export function Binder({ cards }: { cards: MediaCard[] }) {
  return (
    <ul className="cards-binder">
      {cards.map((card) => (
        <li key={card.id}>
          <CardSheet card={card} />
        </li>
      ))}
    </ul>
  );
}

/** Issue 229: ``/cards/sets/:key`` — a set's cards, those owned in colour, the others as their silhouette. */
export default function SetPage() {
  const t = useT();
  const { key } = useParams();
  const set = useCardSet(key);
  if (set.isPending) return <FunctionalState state="loading" />;
  if (!set.data) return <FunctionalState state="error" />;
  const data = set.data;
  return (
    <div className="ds-stack">
      <PageHeader
        icon="layers"
        title={`${data.name}${data.year ? ` (${data.year})` : ""}`}
        context={t("gamification:cards.setLine", { code: data.code, owned: data.owned, size: data.size })}
      />
      <Binder cards={data.cards} />
      <CardCredit />
    </div>
  );
}

/** Issue 229: ``/cards/people?ref=`` — a person's cards, a card per work they are credited on. */
export function PersonPage() {
  const t = useT();
  const [params] = useSearchParams();
  const person = useCardPerson(params.get("ref"));
  if (person.isPending) return <FunctionalState state="loading" />;
  if (!person.data) return <FunctionalState state="error" />;
  return (
    <div className="ds-stack">
      <PageHeader
        icon="user"
        title={person.data.name ?? "?"}
        context={t("gamification:cards.personLine", { owned: person.data.owned, size: person.data.size })}
      />
      <Binder cards={person.data.cards} />
      <CardCredit />
    </div>
  );
}
