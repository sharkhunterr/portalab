import { createContext, type ReactNode, useContext } from "react";

/**
 * Slot provider contracts (spec 004 T025/T036): Search (008), AI assistant (018), notifications (010) and
 * contextual help (011 ``HelpResolver``) plug into the shell through these providers. Until those specs
 * land the shell renders placeholders: search opens the command palette, the assistant shows a degraded
 * state — an AI outage never affects search.
 */
export interface SearchProvider {
  open: (query?: string) => void;
}

export interface AiProvider {
  available: boolean;
  open: (context?: { route: string }) => void;
}

export interface NotificationSummary {
  unread: number;
  open: () => void;
}

export interface HelpResolver {
  resolve: (route: string) => { label: string; href: string } | null;
}

export interface ShellSlots {
  search?: SearchProvider;
  ai?: AiProvider;
  notifications?: NotificationSummary;
  help?: HelpResolver;
}

const SlotsContext = createContext<ShellSlots>({});

export function ShellSlotsProvider({ value, children }: { value: ShellSlots; children: ReactNode }) {
  return <SlotsContext.Provider value={value}>{children}</SlotsContext.Provider>;
}

export function useSlots(): ShellSlots {
  return useContext(SlotsContext);
}
