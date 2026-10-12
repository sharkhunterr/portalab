import type { ThemeDefinition } from "../schema";
// #89: the universes
import academy from "./academy.json";
import alien from "./alien.json";
import caribbean from "./caribbean.json";
import cartoon from "./cartoon.json";
import christmas from "./christmas.json";
import classicdesk from "./classicdesk.json";
import comic from "./comic.json";
import cozy from "./cozy.json";
import cupertino from "./cupertino.json";
import cyberpunk from "./cyberpunk.json";
import dark from "./dark.json";
import desert from "./desert.json";
import disco from "./disco.json";
import futuristic from "./futuristic.json";
import galaxy from "./galaxy.json";
import halloween from "./halloween.json";
import heroes from "./heroes.json";
import highContrast from "./high-contrast.json";
import horror from "./horror.json";
import light from "./light.json";
import manga from "./manga.json";
import matrix from "./matrix.json";
import mecha from "./mecha.json";
import middleearth from "./middleearth.json";
import minimal from "./minimal.json";
import neowave from "./neowave.json";
import nostromo from "./nostromo.json";
import nova from "./nova.json";
import orbit from "./orbit.json";
import plex from "./plex.json";
import portalabDark from "./portalab-dark.json";
import portalabLight from "./portalab-light.json";
import sincity from "./sincity.json";
import social from "./social.json";
import studio from "./studio.json";
import upsidedown from "./upsidedown.json";
import vhs from "./vhs.json";
import wizard from "./wizard.json";

/** Built-in themes (also seeded by the backend ``ui`` migrations; a test keeps both copies identical). */
export const BUILTIN_THEMES: readonly ThemeDefinition[] = [
  portalabDark,
  portalabLight,
  orbit,
  studio,
  light,
  dark,
  highContrast,
  // 027: universe themes
  wizard,
  galaxy,
  matrix,
  desert,
  horror,
  halloween,
  christmas,
  comic,
  manga,
  cartoon,
  cozy,
  futuristic,
  minimal,
  alien,
  heroes,
  neowave,
  disco,
  cyberpunk,
  sincity,
  plex,
  upsidedown,
  middleearth,
  vhs,
  nostromo,
  nova,
  // #89: the universes
  academy,
  caribbean,
  mecha,
  classicdesk,
  cupertino,
  social,
] as ThemeDefinition[];
/** The default theme family (027 R8) and its default member. */
export const DEFAULT_FAMILY = "portalab";
export const DEFAULT_THEME_KEY = "portalab-dark";
export const HIGH_CONTRAST_KEY = "high-contrast";

export function builtinTheme(key: string): ThemeDefinition | undefined {
  return BUILTIN_THEMES.find((theme) => theme.key === key);
}
