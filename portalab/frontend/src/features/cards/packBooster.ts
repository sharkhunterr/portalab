import type { Translate } from "../../i18n/hooks/useT";
import type { Booster } from "../marketplace/boosters/api";
import { demoBooster } from "../marketplace/boosters/BoosterReveal";
import type { PackLook as SealedLook } from "../marketplace/boosters/Boosters";
import { artworkImage, type CardPack } from "./api";

/** The work's title drawn for the member's language: theirs, else English, else one without a language. */
export function logoFor(logos: Record<string, string>, locale: string): string | null {
  const lang = locale.slice(0, 2);
  return logos[lang] ?? logos.en ?? logos[""] ?? Object.values(logos)[0] ?? null;
}

/** Issue 234: a card booster's name — its content (« Dark · Saison 2 »), the works a shop's draws among
 * (« Science-fiction · Films · VHS »), else the whole library. */
export function packName(t: Translate, pack: CardPack): string {
  const look = pack.look;
  if (pack.set_name) {
    return look?.season != null
      ? `${pack.set_name} · ${t("gamification:cards.pack.season", { season: look.season })}`
      : pack.set_name;
  }
  const among = [
    look?.family ? t(`gamification:cards.family.${look.family}`) : null,
    look?.kind ? t(`gamification:cards.pack.kind.${look.kind}`) : null,
    look?.edition ? t(`gamification:cards.edition.${look.edition}`) : null,
  ].filter(Boolean);
  return among.length ? among.join(" · ") : t("gamification:cards.pack.any");
}

/** A card booster as the shop's boosters are: the same sealed pack and stage — its content's title drawn on it
 * (the art site's logo) when there is one. */
export function packBooster(t: Translate, pack: CardPack, locale: string): Booster & SealedLook {
  const name = packName(t, pack);
  const logo = pack.look?.season == null ? artworkImage(logoFor(pack.look?.logos ?? {}, locale)) : null;
  return {
    ...demoBooster({ [locale]: name, en: name }, pack.count),
    key: `cards:${pack.id}`,
    sealed: 1,
    logo,
  };
}
