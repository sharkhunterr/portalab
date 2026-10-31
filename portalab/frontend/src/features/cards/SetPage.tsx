import { Link, useParams, useSearchParams } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { Dialog } from "../../design-system/components/Overlays";
import { PageHeader } from "../../design-system/components/PageHeader";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useT } from "../../i18n/hooks/useT";
import { type MediaCard, useCardPerson, useCardSet, VARIANTS, type Variant } from "./api";
import { CardCredit } from "./CardCredit";
import { MediaCardView } from "./MediaCardView";
import "./cards.css";

/** The best version owned of a card (the one shown in the binder). */
export function best(card: MediaCard): Variant | null {
  return [...VARIANTS].reverse().find((v) => (card.owned[v] ?? 0) > 0) ?? null;
}

/** A card, big, with every version (the borderless alternative is a work's only): the owned ones in colour,
 * how many of each. */
export function CardSheet({ card }: { card: MediaCard }) {
  const t = useT();
  const shown = best(card);
  return (
    <Dialog
      size="lg"
      title={card.name}
      closeLabel={t("gamification:cards.close")}
      trigger={
        <button type="button" className="cards-binder__slot" aria-label={card.name}>
          <MediaCardView card={card} variant={shown ?? "normal"} missing={!shown} size="sm" />
          {Object.values(card.owned).reduce((a, b) => a + (b ?? 0), 0) > 1 ? (
            <span className="cards-binder__count">
              ×{Object.values(card.owned).reduce((a, b) => a + (b ?? 0), 0)}
            </span>
          ) : null}
        </button>
      }
    >
      <div className="cards-sheet">
        {VARIANTS.filter((v) =>
          v.startsWith("borderless")
            ? card.kind === "title" && card.rarity !== "common"
            : v.startsWith("showcase")
              ? Boolean(card.set_edition)
              : v === "hd"
                ? card.rarity === "legendary" && Boolean(card.set_edition) // issue 255
                : true,
        ).map((variant) => (
          <figure key={variant} data-owned={(card.owned[variant] ?? 0) > 0 || undefined}>
            <MediaCardView card={card} variant={variant} missing={!(card.owned[variant] ?? 0)} />
            <figcaption>
              {t(`gamification:cards.variant.${variant}`, {
                edition: card.set_edition ? t(`gamification:cards.edition.${card.set_edition}`) : "",
                genre: t(`gamification:cards.family.${card.set_family ?? "drama"}`),
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
