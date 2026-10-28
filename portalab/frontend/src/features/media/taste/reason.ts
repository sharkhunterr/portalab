import type { Translate } from "../../../i18n/hooks/useT";
import type { TasteReason } from "./api";

const KNOWN = new Set([
  "saga",
  "franchise",
  "director",
  "creator",
  "cast",
  "author",
  "narrator",
  "writer",
  "genre",
  "keyword",
  "studio",
  "publisher",
  "platform",
  "country",
  "rated",
  "detour", // off my beaten track: a genre I seldom go to
  "bridge", // a medium I do not use yet, by a saga or an author I love
]);

/**
 * Issue 190: why a title is offered, in a few words (« Saga Hunger Games », « By Peter Jackson ») and, beside
 * it, the titles of mine it comes from (« Like Inception and Interstellar »).
 */
export function reasonOf(
  reason: TasteReason | null | undefined,
  t: Translate,
  list: (items: string[]) => string,
  region: (code: string) => string = (code) => code,
): { short: string; like: string | null } | null {
  if (!reason || !KNOWN.has(reason.kind)) return null;
  const name = reason.kind === "country" && reason.name ? region(reason.name) : (reason.name ?? "");
  const titles = reason.titles ?? [];
  return {
    short: t(`media:taste.reason.${reason.kind}`, { name }),
    like: titles.length ? t("media:taste.reason.like", { titles: list(titles) }) : null,
  };
}
