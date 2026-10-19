import { createContext, useContext } from "react";

/**
 * Issue 159: what the site's identity changes in the design system — the currency's icon (in place of the
 * coins, unless the member's theme swaps it) and its short name beside compact amounts (« 120 XC »).
 * Provided by the shell from the site's identity; empty, Portalab's own.
 */
export interface SiteLook {
  currencyIcon: string | null;
  currencyShort: string | null;
}

export const SiteLookContext = createContext<SiteLook>({ currencyIcon: null, currencyShort: null });

export function useSiteLook(): SiteLook {
  return useContext(SiteLookContext);
}

/** The currency's short name after a compact amount — nothing while the site has none. */
export function CurrencyShort() {
  const { currencyShort } = useSiteLook();
  return currencyShort ? <span className="ds-currency-short">{` ${currencyShort}`}</span> : null;
}
