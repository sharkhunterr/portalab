import type { CSSProperties, PointerEvent } from "react";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { artworkImage, cardImage, type MediaCard, type Variant } from "./api";
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

/** Issue 229: where the light falls on a foil card, and how it leans — it follows the pointer: the card turns
 * towards it, the holographic stripes slide the other way, the sparkles a little, brighter off the centre. */
function tilt(event: PointerEvent<HTMLElement>) {
  const box = event.currentTarget.getBoundingClientRect();
  const x = Math.min(1, Math.max(0, (event.clientX - box.left) / box.width));
  const y = Math.min(1, Math.max(0, (event.clientY - box.top) / box.height));
  const style = event.currentTarget.style;
  style.setProperty("--mcard-x", `${x * 100}%`);
  style.setProperty("--mcard-y", `${y * 100}%`);
  style.setProperty("--mcard-rx", `${(0.5 - y) * 20}deg`);
  style.setProperty("--mcard-ry", `${(x - 0.5) * 24}deg`);
  style.setProperty("--mcard-bx", `${(1 - x) * 100}%`);
  style.setProperty("--mcard-by", `${(1 - y) * 100}%`);
  style.setProperty("--mcard-sx", `${50 + (0.5 - x) * 10}%`);
  style.setProperty("--mcard-sy", `${50 + (0.5 - y) * 10}%`);
  style.setProperty("--mcard-glare", String(0.35 + Math.hypot(x - 0.5, y - 0.5) * 1.1));
  event.currentTarget.dataset.active = "";
}

/** The pointer gone: the card settles back, its light idles. */
function rest(event: PointerEvent<HTMLElement>) {
  delete event.currentTarget.dataset.active;
  for (const name of ["--mcard-rx", "--mcard-ry", "--mcard-bx", "--mcard-by", "--mcard-sx", "--mcard-sy"]) {
    event.currentTarget.style.removeProperty(name);
  }
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
  // an actor's card shows their character in this work (once found); without one (issue 231), the work's
  // poster and their portrait in a round badge — clearly not the character. The borderless alternative:
  // another image of the character, else their portrait
  const stand_in = !borderless && card.kind === "cast" && !card.role_art && Boolean(card.set_poster);
  const art = borderless
    ? card.kind === "title"
      ? (artworkImage(card.fan_art) ?? cardImage(card.alt_art ?? card.art, "w780"))
      : card.role_alt || card.role_art
        ? cardImage(card.role_alt ?? card.role_art, "w780")
        : cardImage(card.art, "h632") // never an image of the work: it shows someone else
    : card.role_art
      ? cardImage(card.role_art, "w780")
      : stand_in
        ? cardImage(card.set_poster ?? null, "w500")
        : cardImage(card.art, card.kind === "title" ? "w500" : "h632");
  const portrait = stand_in ? cardImage(card.art, "w185") : null;
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
      onPointerLeave={foil ? rest : undefined}
      aria-label={`${card.name} — ${type}`}
    >
      <div className="mcard__card">
        <div
          className="mcard__art"
          data-art={!borderless && card.role_art ? "role" : stand_in ? "poster" : undefined}
        >
          {art ? (
            <img className="mcard__picture" src={art} alt="" loading="lazy" draggable={false} />
          ) : (
            <Icon name={KIND_ICON[card.kind]} size={size === "sm" ? 24 : 40} />
          )}
          {portrait ? (
            <img className="mcard__badge" src={portrait} alt="" loading="lazy" draggable={false} />
          ) : null}
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
        {foil ? (
          <>
            <span className="mcard__foil" aria-hidden="true" />
            <span className="mcard__sparkle" aria-hidden="true" />
          </>
        ) : null}
      </div>
    </article>
  );
}
