import type { ReactNode } from "react";

/**
 * Placeholder shell (spec 001 US1). The real persistent shell — dynamic navigation, search/AI entries,
 * command palette, global states — is built by spec 004 on top of this landmark layout.
 * No business logic lives here.
 */
export interface AppShellProps {
  navigation?: ReactNode;
  children: ReactNode;
}

export function AppShell({ navigation, children }: AppShellProps) {
  return (
    <>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="border-b border-border px-4 py-3">
        <span className="text-lg font-semibold">Portalab</span>
      </header>
      <div className="flex min-h-screen">
        <nav aria-label="Main navigation" className="w-56 border-r border-border p-4">
          {navigation ?? <p className="text-text-muted">Navigation</p>}
        </nav>
        <main id="main-content" tabIndex={-1} className="flex-1 p-4">
          {children}
        </main>
      </div>
    </>
  );
}
