import type { PointerEvent } from "react";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import "@fontsource/barlow-condensed/latin-600.css";
import "@fontsource/barlow-condensed/latin-700.css";
import { artworkImage, cardImage, type MediaCard, type Variant } from "./api";
import { gaugesOf } from "./gauges";
import "./cards.css";

const KIND_ICON: Record<MediaCard["kind"], string> = {
  title: "film",
  director: "clapperboard",
  creator: "clapperboard",
  cast: "user",
  writer: "feather",
  composer: "music",
};
const SEGMENTS = Array.from({ length: 10 }, (_, i) => i);
const VOICE = /\((voice|voix)\)/i;

/** The size of a name so that it fits its plate whole (container units), wrapping on two lines at the least. */
function fit(text: string, room: number, largest: number, smallest: number, width = 0.46): string {
  const size = room / (Math.max(text.length, 1) * width);
  return `${Math.max(smallest, Math.min(largest, size)).toFixed(2)}cqi`;
}

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
 * Issue 229: a media card, printed like a modern trading card game's. Its body takes its work's genre colour
 * (science fiction blue, action red, fantasy violet, family green, drama ivory, crime charcoal, several strong
 * genres gold); a metallic rim, a gem and a written name say its rarity (steel, silver, gold, holographic).
 * On top its name, whole — a role's card is the character's, its actor in the plate at the bottom; then its
 * art with its type and rarity over it; three gauges of the work's own figures, frozen with the set; a line
 * of flavour when the work has one. ``borderless``: the art over the whole card, the plates in glass;
 * ``foil``: a holographic light that follows the pointer. A card not owned yet shows dimmed. A role without
 * an image of its character shows the work's poster and the actor's portrait in a round badge.
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
  const series = card.set_kind === "series";
  const voice = card.kind === "cast" && (VOICE.test(card.role ?? "") || Boolean(card.set_animated));
  // a role's card is its character's: the actor goes to the plate at the bottom
  const character = card.kind === "cast" ? (card.role ?? "").replace(VOICE, "").trim() : "";
  const title = character || card.name;
  const type =
    card.kind === "title"
      ? t(`gamification:cards.type.${series ? "series" : "movie"}`, { year: card.year ?? "" })
      : t("gamification:cards.type.of", {
          kind: t(`gamification:cards.type.${character ? "character" : card.kind}`),
          title: card.set_name,
        });
  const credit =
    card.kind === "title"
      ? card.set_facts?.director
        ? {
            label: t(`gamification:cards.credit.${series ? "series" : "movie"}`),
            name: card.set_facts.director,
          }
        : null
      : card.kind === "cast"
        ? { label: t(`gamification:cards.credit.${voice ? "voice" : "cast"}`), name: card.name }
        : { label: t(`gamification:cards.credit.${card.kind}`), name: card.set_name };
  const gauges = size === "sm" ? [] : gaugesOf(card);
  const collector = `${String(card.number).padStart(3, "0")}/${String(card.set_size).padStart(3, "0")} · ${card.set_code}`;
  return (
    <article
      className="mcard"
      data-size={size}
      data-kind={card.kind}
      data-family={card.set_family ?? "drama"}
      data-rarity={card.rarity}
      data-borderless={borderless || undefined}
      data-foil={foil || undefined}
      data-missing={missing || undefined}
      onPointerMove={foil ? tilt : undefined}
      onPointerLeave={foil ? rest : undefined}
      aria-label={`${title} — ${type}`}
    >
      <div className="mcard__card">
        <div className="mcard__body">
          <header className="mcard__name">
            <span style={{ fontSize: fit(title, 74, 8.4, 4.6) }}>{title}</span>
            <span className="mcard__sign" aria-hidden="true">
              <Icon name={KIND_ICON[card.kind]} size={12} />
            </span>
          </header>
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
            <div className="mcard__type">
              <span style={{ fontSize: fit(type, 46, 4, 3, 0.62) }}>{type}</span>
              <span className="mcard__rarity">
                <span className="mcard__gem" aria-hidden="true" />
                {t(`gamification:cards.rarity.${card.rarity}`)}
              </span>
            </div>
          </div>
          {gauges.length || card.flavor ? (
            <div className="mcard__stats">
              {gauges.map((gauge) => (
                <div className="mcard__gauge" key={gauge.key}>
                  <span>
                    {t(
                      gauge.key === "work"
                        ? `gamification:cards.gauge.work.${series ? "series" : "movie"}`
                        : `gamification:cards.gauge.${gauge.key}`,
                    )}
                  </span>
                  <span className="mcard__segments" aria-hidden="true">
                    {SEGMENTS.map((i) => (
                      <span key={i} data-on={gauge.filled !== null && i < gauge.filled ? "" : undefined} />
                    ))}
                  </span>
                  <span data-unknown={gauge.value ? undefined : ""}>
                    {gauge.value ? t(gauge.value.id, gauge.value.values) : "—"}
                  </span>
                </div>
              ))}
              {card.flavor && size !== "sm" ? <p className="mcard__flavor">{card.flavor}</p> : null}
            </div>
          ) : null}
          <footer className="mcard__credit">
            <span>
              {credit ? (
                <>
                  <small>{credit.label}</small>
                  <strong style={{ fontSize: fit(credit.name, 52, 4.8, 3.4) }}>{credit.name}</strong>
                </>
              ) : (
                <strong>{card.year ?? ""}</strong>
              )}
            </span>
            <span className="mcard__collector">
              <span>{collector}</span>
              <span>{foil ? "★ TMDB" : "TMDB"}</span>
            </span>
          </footer>
        </div>
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
