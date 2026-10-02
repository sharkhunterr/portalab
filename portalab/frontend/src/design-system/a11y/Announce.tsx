import { createContext, type ReactNode, useCallback, useContext, useMemo, useState } from "react";

/**
 * Live-region announcer (spec 022 T028): async results and critical state changes are announced to
 * assistive technologies — ``polite`` for results, ``assertive`` for critical changes. Messages are
 * re-announced even when identical (a counter key forces a new node).
 */
type Politeness = "polite" | "assertive";

interface AnnounceContextValue {
  announce: (message: string, politeness?: Politeness) => void;
}

const AnnounceContext = createContext<AnnounceContextValue>({ announce: () => undefined });

export function AnnounceProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<{ polite: [number, string]; assertive: [number, string] }>({
    polite: [0, ""],
    assertive: [0, ""],
  });
  const announce = useCallback((message: string, politeness: Politeness = "polite") => {
    setMessages((current) => ({ ...current, [politeness]: [current[politeness][0] + 1, message] }));
  }, []);
  const value = useMemo(() => ({ announce }), [announce]);
  return (
    <AnnounceContext.Provider value={value}>
      {children}
      <div className="visually-hidden" aria-live="polite" aria-atomic="true" data-testid="announce-polite">
        <span key={messages.polite[0]}>{messages.polite[1]}</span>
      </div>
      <div
        className="visually-hidden"
        aria-live="assertive"
        aria-atomic="true"
        data-testid="announce-assertive"
      >
        <span key={messages.assertive[0]}>{messages.assertive[1]}</span>
      </div>
    </AnnounceContext.Provider>
  );
}

export function useAnnounce(): AnnounceContextValue["announce"] {
  return useContext(AnnounceContext).announce;
}
