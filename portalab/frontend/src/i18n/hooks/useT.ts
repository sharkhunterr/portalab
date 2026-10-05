import { IntlMessageFormat } from "intl-messageformat";
import { useContext, useMemo } from "react";
import { IntlContext } from "react-intl";
import { BUNDLED_MESSAGES } from "../bundled";
import { useVocabulary } from "./vocabulary";

/**
 * ``useT()`` (spec 026 T018): ``t("namespace:key", values)`` renders an ICU message of the active
 * language; outside an ``I18nProvider`` (tests, first paint) it renders the bundled English text. A missing
 * key renders its English fallback, then the key itself — never an empty string, never an exception.
 */
export type Translate = (id: string, values?: Record<string, string | number>) => string;

const cache = new Map<string, IntlMessageFormat>();

function fallback(id: string, values?: Record<string, string | number>): string {
  const source = BUNDLED_MESSAGES[id];
  if (source === undefined) return id.includes(":") ? (id.split(":").slice(1).join(":") as string) : id;
  try {
    let format = cache.get(id);
    if (!format) {
      format = new IntlMessageFormat(source, "en");
      cache.set(id, format);
    }
    return String(format.format(values));
  } catch {
    return source;
  }
}

export function useT(): Translate {
  const intl = useContext(IntlContext);
  const vocabulary = useVocabulary();
  return useMemo<Translate>(() => {
    if (!intl) return fallback;
    return (id, values) => {
      const themed = vocabulary[id]; // 027: the active theme's word for it
      if (themed) return themed;
      if (!intl.messages[id]) return fallback(id, values);
      try {
        return intl.formatMessage({ id, defaultMessage: BUNDLED_MESSAGES[id] ?? id }, values) as string;
      } catch {
        return fallback(id, values);
      }
    };
  }, [intl, vocabulary]);
}
