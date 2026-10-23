import { useContext } from "react";
import { IntlContext } from "react-intl";
import { useT } from "../../i18n/hooks/useT";
import "@fontsource/anton/latin-400.css";
import "@fontsource/cinzel/latin-700.css";
import "@fontsource/creepster/latin-400.css";
import "@fontsource/fredoka/latin-700.css";
import "@fontsource/orbitron/latin-700.css";
import "@fontsource/playfair-display/latin-700.css";
import { artworkImage, type CardPack, cardImage } from "./api";
import "./cards.css";

/** The work's title drawn for the member's language: theirs, else English, else one without a language. */
export function logoFor(logos: Record<string, string>, locale: string): string | null {
  const lang = locale.slice(0, 2);
  return logos[lang] ?? logos.en ?? logos[""] ?? Object.values(logos)[0] ?? null;
}

/**
 * Issue 234: a sealed booster, as a pack of cards in a shop — a content's wears its work: one of its scenes,
 * its title drawn (the art site's logo, else its name in its genre's type), the season it was for, its
 * edition's symbol and how many cards it holds; a booster of the whole library, the portal's own.
 */
export function CardBooster({ pack }: { pack: CardPack }) {
  const t = useT();
  const locale = useContext(IntlContext)?.locale ?? "en";
  const look = pack.look ?? null;
  const scene = look ? (cardImage(look.backdrop, "w780") ?? cardImage(look.poster, "w500")) : null;
  const logo = look ? artworkImage(logoFor(look.logos, locale)) : null;
  // a shop's booster: the works it draws among (a genre, films or series), else the whole library
  const among = look?.product
    ? [
        look.family ? t(`gamification:cards.family.${look.family}`) : null,
        look.kind ? t(`gamification:cards.pack.kind.${look.kind}`) : null,
      ].filter(Boolean)
    : [];
  const name = pack.set_name ?? (among.length ? among.join(" · ") : t("gamification:cards.pack.any"));
  return (
    <span
      className="cbooster"
      data-family={look?.family ?? undefined}
      data-edition={look?.edition ?? undefined}
      data-source={pack.source}
    >
      <span className="cbooster__crimp" aria-hidden="true" />
      <span className="cbooster__body">
        {scene ? (
          <img className="cbooster__scene" src={scene} alt="" loading="lazy" draggable={false} />
        ) : null}
        <span className="cbooster__sheen" aria-hidden="true" />
        <span className="cbooster__title">
          {logo ? (
            <img className="cbooster__logo" src={logo} alt={name} loading="lazy" draggable={false} />
          ) : (
            <span className="cbooster__name">{name}</span>
          )}
        </span>
        {look?.product && look.edition ? (
          <span className="cbooster__season">{t(`gamification:cards.edition.${look.edition}`)}</span>
        ) : null}
        {look?.season != null ? (
          <span className="cbooster__season">
            {t("gamification:cards.pack.season", { season: look.season })}
          </span>
        ) : null}
        <span className="cbooster__band">
          <span className="cbooster__count">{t("gamification:cards.pack.cards", { count: pack.count })}</span>
          {look?.code ? <span className="cbooster__code">{look.code}</span> : null}
          {look?.edition ? (
            <span
              className="cbooster__edition"
              role="img"
              aria-label={t(`gamification:cards.edition.${look.edition}`)}
            />
          ) : null}
        </span>
      </span>
      <span className="cbooster__crimp" aria-hidden="true" />
    </span>
  );
}
