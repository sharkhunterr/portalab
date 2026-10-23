import type { CSSProperties, PointerEvent, SyntheticEvent } from "react";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import "@fontsource/barlow-condensed/latin-600.css";
import "@fontsource/barlow-condensed/latin-700.css";
import { artworkImage, cardImage, type MediaCard, type Variant } from "./api";
import { figuresOf, runtimeParts } from "./figures";
import "./cards.css";

const KIND_ICON: Record<MediaCard["kind"], string> = {
  title: "film",
  director: "clapperboard",
  creator: "clapperboard",
  cast: "user",
  writer: "feather",
  composer: "music",
};
// the genre's emblem, like a trading card's type symbol
const FAMILY_ICON: Record<string, string> = {
  sf: "rocket",
  action: "swords",
  fantasy: "sparkles",
  family: "smile",
  drama: "drama",
  dark: "skull",
};
const VOICE = /\((voice|voix)\)/i;

/** The size of a name so that it fits its room whole on one line (container units): only a long one is smaller. */
function fit(text: string, room: number, largest: number, smallest: number, width = 0.46): string {
  const size = room / (Math.max(text.length, 1) * width);
  return `${Math.max(smallest, Math.min(largest, size)).toFixed(2)}cqi`;
}

/** Issue 229: where the light falls on a foil card, and how it leans — it follows the pointer: the card turns
 * towards it, the rainbow film and the glare follow it. */
function tilt(event: PointerEvent<HTMLElement>) {
  const box = event.currentTarget.getBoundingClientRect();
  const x = Math.min(1, Math.max(0, (event.clientX - box.left) / box.width));
  const y = Math.min(1, Math.max(0, (event.clientY - box.top) / box.height));
  const style = event.currentTarget.style;
  style.setProperty("--mcard-px", `${x * 100}%`);
  style.setProperty("--mcard-py", `${y * 100}%`);
  style.setProperty("--mcard-rx", `${(0.5 - y) * 22}deg`);
  style.setProperty("--mcard-ry", `${(x - 0.5) * 26}deg`);
  event.currentTarget.dataset.active = "";
}

/** The colour along one side of an image (its average), or null when it cannot be read. */
function sideColour(context: CanvasRenderingContext2D, x: number): string | null {
  const data = context.getImageData(x, 0, 1, 8).data;
  const sum = [0, 1, 2].map((channel) => {
    let total = 0;
    for (let index = channel; index < data.length; index += 4) total += data[index] ?? 0;
    return Math.round(total / 8);
  });
  return `#${sum.map((value) => value.toString(16).padStart(2, "0")).join("")}`;
}

/** The image framed on its face (found by the server: the centre of its largest face, as fractions of it): the
 * face across the middle and two fifths down the window, as far as the image reaches. */
function frameFace(image: HTMLImageElement) {
  const at = [Number(image.dataset.fx), Number(image.dataset.fy)];
  const width = image.clientWidth;
  const height = image.clientHeight;
  if (!image.dataset.fy || !width || !height || !image.naturalWidth || !image.naturalHeight) return;
  const scale = Math.max(width / image.naturalWidth, height / image.naturalHeight);
  const place = (natural: number, box: number, centre: number, target: number) => {
    const room = natural * scale - box;
    if (room <= 1) return 50;
    return (Math.min(room, Math.max(0, centre * natural * scale - target * box)) / room) * 100;
  };
  const x = place(image.naturalWidth, width, at[0] ?? 0.5, 0.5);
  const y = place(image.naturalHeight, height, at[1] ?? 0.4, 0.4);
  image.style.objectPosition = `${x.toFixed(1)}% ${y.toFixed(1)}%`;
}

/** An upright image (a portrait, a poster) in the art's wide window: zoomed out, from the head down, its sides
 * fading into its own edges' colours (a portrait's backdrop carried on) — its art says so once it is known. */
function measure(event: SyntheticEvent<HTMLImageElement>) {
  const image = event.currentTarget;
  const upright = image.naturalHeight > image.naturalWidth * 1.15;
  const art = image.parentElement;
  if (!art) return;
  art.dataset.shape = upright ? "upright" : "wide";
  frameFace(image);
  if (!upright) return;
  try {
    const canvas = document.createElement("canvas");
    canvas.width = 4;
    canvas.height = 8;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context) return;
    context.drawImage(image, 0, 0, 4, 8);
    const start = sideColour(context, 0);
    const end = sideColour(context, 3);
    if (start) art.style.setProperty("--mcard-art-start", start);
    if (end) art.style.setProperty("--mcard-art-end", end);
  } catch {
    // an image that cannot be read: the window's own colour on its sides
  }
}

/** The pointer gone: the card sways on its own again. */
function rest(event: PointerEvent<HTMLElement>) {
  delete event.currentTarget.dataset.active;
  for (const name of ["--mcard-px", "--mcard-py", "--mcard-rx", "--mcard-ry"]) {
    event.currentTarget.style.removeProperty(name);
  }
}

/**
 * Issue 229: a media card, laid out like a trading card game's. Its rim is its rarity's metal; its body its
 * work's genre colour (the genre's emblem and name top right). On top its name, whole on one line; its art in a
 * metal frame; under it, in a band, what it is — simply (a character, a film, a director) — and its edition's
 * symbol; then the work it belongs to: its poster the whole height on the left, who plays it, its title, year
 * and figures on the right (the figures as a card's attacks: the work's rating, box office…); at the foot its collector number and
 * its rarity. The same card at every size. ``borderless``: the art over the whole card, only its name, the band
 * and its rarity over it;
 * ``foil``: a holographic light that follows the pointer. A card not owned yet shows dimmed. A role
 * without an image of its character shows the work's poster and the actor's portrait in a round badge.
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
  const foil = variant === "foil" || variant.endsWith("_foil");
  // issue 233: its edition's version wears the edition's frame (a visual pack's ``card_frame``)
  const edition = card.set_edition ?? null;
  const showcase = (variant === "showcase" || variant === "showcase_foil") && Boolean(edition);
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
  // where the face is in the image shown (its character's, or the person's portrait)
  const shown = borderless ? null : (card.role_art ?? (stand_in || card.kind === "title" ? null : card.art));
  const face = shown ? (card.focus?.[shown] ?? null) : null;
  const facts = card.set_facts ?? {};
  const series = card.set_kind === "series";
  const family = card.set_family ?? "drama";
  const voice = card.kind === "cast" && (VOICE.test(card.role ?? "") || Boolean(card.set_animated));
  // a role's card is its character's: the actor is named under the art
  const character = card.kind === "cast" ? (card.role ?? "").replace(VOICE, "").trim() : "";
  const title = character || card.name;
  const stage = t(
    `gamification:cards.stage.${card.kind === "title" ? (series ? "series" : "movie") : card.kind}`,
  );
  const strip =
    card.kind === "cast"
      ? t(`gamification:cards.strip.${voice ? "voice" : "cast"}`, {
          name: card.name,
          place: (card.billing ?? 0) + 1,
        })
      : card.kind === "title" && facts.director
        ? t(`gamification:cards.strip.${series ? "series" : "movie"}`, { name: facts.director })
        : null;
  const runtime = runtimeParts(facts.runtime);
  const meta = [
    card.year ? String(card.year) : null,
    runtime ? t("gamification:cards.runtime", runtime) : null,
    ...(facts.genres ?? []).slice(0, 2),
  ]
    .filter(Boolean)
    .join(" · ");
  const poster = card.kind !== "title" && !stand_in ? cardImage(card.set_poster ?? null, "w185") : null;
  const figures = figuresOf(card);
  const genre = t(`gamification:cards.family.${family}`);
  // the name's room: the card's inner width, less the genre's chip (its emblem and its name)
  const room = 84 - 9 - genre.length * 2.1;
  return (
    <article
      className="mcard"
      data-size={size}
      data-kind={card.kind}
      data-family={family}
      data-rarity={card.rarity}
      data-borderless={borderless || undefined}
      data-edition={edition ?? undefined}
      data-frame={showcase ? `edition-${edition}` : undefined}
      data-foil={foil || undefined}
      data-missing={missing || undefined}
      onPointerMove={foil ? tilt : undefined}
      onPointerLeave={foil ? rest : undefined}
      // foil cards side by side don't sway together
      style={foil ? ({ "--mcard-phase": `${-((card.number * 2.3) % 9)}s` } as CSSProperties) : undefined}
      aria-label={`${title} — ${stage}`}
    >
      <div className="mcard__card">
        <div className="mcard__body">
          <header className="mcard__head">
            <span className="mcard__name" style={{ fontSize: fit(title, room, 8.6, 3.6) }}>
              {title}
            </span>
            <span className="mcard__genre">
              <span className="mcard__emblem" aria-hidden="true">
                <Icon name={FAMILY_ICON[family] ?? "star"} size={14} />
              </span>
              {genre}
            </span>
          </header>
          <div
            className="mcard__art"
            data-art={!borderless && card.role_art ? "role" : stand_in ? "poster" : undefined}
          >
            {art ? (
              <img
                className="mcard__picture"
                src={art}
                alt=""
                loading="lazy"
                draggable={false}
                onLoad={borderless ? undefined : measure}
                data-fx={face ? face[0] : undefined}
                data-fy={face ? face[1] : undefined}
              />
            ) : (
              <Icon name={KIND_ICON[card.kind]} size={40} />
            )}
            {portrait ? (
              <img className="mcard__badge" src={portrait} alt="" loading="lazy" draggable={false} />
            ) : null}
          </div>
          <p className="mcard__strip">
            <span className="mcard__stage">{stage}</span>
            {/* who plays it: in the box under it, or over the art on a borderless card */}
            {borderless && strip ? <span className="mcard__by">{strip}</span> : null}
            {edition ? (
              <span
                className="mcard__edition"
                role="img"
                aria-label={t(`gamification:cards.edition.${edition}`)}
                title={t(`gamification:cards.edition.${edition}`)}
              />
            ) : null}
          </p>
          {borderless ? null : (
            <div className="mcard__lower">
              {poster ? (
                <span className="mcard__poster">
                  <img src={poster} alt="" loading="lazy" draggable={false} />
                </span>
              ) : null}
              <div className="mcard__facts">
                {strip ? <p className="mcard__by">{strip}</p> : null}
                {card.kind === "title" ? (
                  meta ? (
                    <p className="mcard__meta">{meta}</p>
                  ) : null
                ) : (
                  <div className="mcard__work">
                    <strong style={{ fontSize: fit(card.set_name, poster ? 100 : 150, 5, 3.4, 0.5) }}>
                      {card.set_name}
                    </strong>
                    {meta ? <small>{meta}</small> : null}
                  </div>
                )}
                {figures.length ? (
                  <ul className="mcard__figures">
                    {figures.map((figure) => (
                      <li key={figure.key}>
                        <span className="mcard__cost" aria-hidden="true">
                          <Icon name={figure.icon} size={10} />
                        </span>
                        <span>
                          {t(
                            figure.key === "rating" && card.kind !== "title"
                              ? `gamification:cards.figure.workRating.${series ? "series" : "movie"}`
                              : `gamification:cards.figure.${figure.key}`,
                          )}
                        </span>
                        <strong>
                          {t(figure.big.id, figure.big.values)}
                          {figure.small ? <small>{figure.small}</small> : null}
                        </strong>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </div>
          )}
          {!borderless && card.kind === "title" && card.flavor ? (
            <p className="mcard__flavor">{card.flavor}</p>
          ) : null}
          <footer className="mcard__foot">
            <span>
              {String(card.number).padStart(3, "0")}/{String(card.set_size).padStart(3, "0")} ·{" "}
              {card.set_code}
              {foil ? " ★" : ""}
            </span>
            <span className="mcard__rarity">
              <span className="mcard__gem" aria-hidden="true" />
              {t(`gamification:cards.rarity.${card.rarity}`)}
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
