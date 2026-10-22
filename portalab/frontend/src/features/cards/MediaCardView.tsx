import type { CSSProperties, PointerEvent } from "react";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { cardImage, type MediaCard, type Variant } from "./api";
import "./cards.css";

const KIND_ICON: Record<MediaCard["kind"], string> = {
  title: "film",
  director: "clapperboard",
  creator: "clapperboard",
  cast: "user",
  writer: "feather",
  composer: "music",
};
const RARITY_LETTER = { common: "C", rare: "R", epic: "E", legendary: "L" } as const;

/** Where the light falls on a foil card: it follows the pointer. */
function tilt(event: PointerEvent<HTMLElement>) {
  const box = event.currentTarget.getBoundingClientRect();
  event.currentTarget.style.setProperty("--mcard-x", `${((event.clientX - box.left) / box.width) * 100}%`);
  event.currentTarget.style.setProperty("--mcard-y", `${((event.clientY - box.top) / box.height) * 100}%`);
}

/**
 * Issue 229: a media card, drawn like a trading card game's — its name and kind's sign on top, its art, its
 * type line with the set's symbol in its rarity's colour, a line of flavour, its collector number. The frame's
 * colour says its kind (the work gold, a director red, the cast blue…). ``borderless``: the alternative —
 * the art over the whole card, the texts on it; ``foil``: a light that moves with the pointer. A card not owned
 * yet shows dimmed. A person's card shows their portrait (until their character's image is found).
 */
export function MediaCardView({
  card,
  variant = "normal",
  missing = false,
  size = "md",
}: {
  card: MediaCard;
  variant?: Variant;
  missing?: boolean;
  size?: "sm" | "md" | "lg";
}) {
  const t = useT();
  const borderless = variant === "borderless" || variant === "borderless_foil";
  const foil = variant === "foil" || variant === "borderless_foil";
  // an actor's card shows their character in this work (once found), else their portrait; the borderless
  // alternative another image of the character, else one of the work
  const art = borderless
    ? card.kind === "title"
      ? cardImage(card.alt_art ?? card.art, "w780")
      : card.role_alt || card.role_art
        ? cardImage(card.role_alt ?? card.role_art, "w780")
        : cardImage(card.art, "h632") // never an image of the work: it shows someone else
    : card.role_art
      ? cardImage(card.role_art, "w780")
      : cardImage(card.art, card.kind === "title" ? "w500" : "h632");
  const type =
    card.kind === "title"
      ? t(`gamification:cards.type.${card.set_kind === "series" ? "series" : "movie"}`, {
          year: card.year ?? "",
        })
      : card.kind === "cast" && card.role
        ? `${t(`gamification:cards.type.${card.kind}`)} — ${card.role}` // the character played
        : t(`gamification:cards.type.${card.kind}`);
  const flavor =
    card.kind === "title"
      ? card.flavor
      : t("gamification:cards.in", { title: card.set_name, year: card.year ?? "" });
  return (
    <article
      className="mcard"
      data-size={size}
      data-kind={card.kind}
      data-rarity={card.rarity}
      data-borderless={borderless || undefined}
      data-foil={foil || undefined}
      data-missing={missing || undefined}
      onPointerMove={foil ? tilt : undefined}
      aria-label={`${card.name} — ${type}`}
    >
      <div className="mcard__card">
        <div className="mcard__art" data-art={!borderless && card.role_art ? "role" : undefined}>
          {art ? (
            <img className="mcard__picture" src={art} alt="" loading="lazy" draggable={false} />
          ) : (
            <Icon name={KIND_ICON[card.kind]} size={size === "sm" ? 24 : 40} />
          )}
        </div>
        <header className="mcard__name">
          <span>{card.name}</span>
          <span className="mcard__sign" aria-hidden="true">
            <Icon name={KIND_ICON[card.kind]} size={12} />
          </span>
        </header>
        <div className="mcard__type">
          <span>{type}</span>
          <span
            className="mcard__symbol"
            title={t(`gamification:cards.rarity.${card.rarity}`)}
            style={{ "--mcard-rarity": `var(--card-symbol-${card.rarity})` } as CSSProperties}
          >
            {card.set_code}
          </span>
        </div>
        {size !== "sm" ? <p className="mcard__text">{flavor}</p> : null}
        <footer className="mcard__foot">
          <span>
            {String(card.number).padStart(3, "0")}/{String(card.set_size).padStart(3, "0")}{" "}
            {RARITY_LETTER[card.rarity]}
          </span>
          <span>
            {card.set_code}
            {foil ? " ★" : ""} · TMDB
          </span>
        </footer>
        {foil ? <span className="mcard__foil" aria-hidden="true" /> : null}
      </div>
    </article>
  );
}
