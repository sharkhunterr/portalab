import { createContext, useContext } from "react";

/**
 * Theme vocabulary (027): a theme may rename some portal words for its universe — the navigation, page
 * titles, the currency (« Coins » → « Gallions »). Plain-text terms of the active language, keyed by message
 * id; anything not renamed keeps its translation. Provided by the appearance root from the active theme.
 */
export type Vocabulary = Readonly<Record<string, string>>;

export const VocabularyContext = createContext<Vocabulary>({});

export function useVocabulary(): Vocabulary {
  return useContext(VocabularyContext);
}
