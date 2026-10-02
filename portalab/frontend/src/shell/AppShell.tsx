import { type ReactNode, useEffect, useMemo, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router";
import { Dialog } from "../design-system/components/Overlays";
import { Breadcrumbs, RelatedLinks } from "./breadcrumbs/Breadcrumbs";
import { ResponsiveNav } from "./nav/ResponsiveNav";
import { CommandPalette } from "./palette/CommandPalette";
import { PaletteContext } from "./palette/PaletteContext";
import { RegionBoundary } from "./router/RouteBoundary";
import { ShortcutManager } from "./shortcuts/ShortcutManager";
import { AiEntry, HelpEntry, IdentityMenu, NotificationEntry, SearchEntry } from "./slots/Entries";
import { GlobalStatusBanner } from "./status/GlobalStatusBanner";
import { useShellStrings } from "./strings";

/**
 * Persistent shell (spec 004 T017; R1, FR-001..004): one environment for every module — header (search,
 * assistant, notifications, identity), primary navigation, global status banner, breadcrumbs and the page
 * outlet. Only the outlet changes on navigation; the shell stays mounted and keeps its state. Unknown to
 * anonymous visitors (the router renders only after sign-in, CD-025).
 */
export interface AppShellProps {
  userName: string;
  onSignOut: () => void;
  shortcutOverrides?: Record<string, string>;
  sidebarCollapsed?: boolean;
  children?: ReactNode;
}

export function AppShell({
  userName,
  onSignOut,
  shortcutOverrides = {},
  sidebarCollapsed = false,
  children,
}: AppShellProps) {
  const shellStrings = useShellStrings();
  const navigate = useNavigate();
  const location = useLocation();
  const [palette, setPalette] = useState<{ open: boolean; query: string }>({ open: false, query: "" });
  const [helpOpen, setHelpOpen] = useState(false);
  const control = useMemo(
    () => ({
      open: (query = "") => setPalette({ open: true, query }),
      openShortcuts: () => setHelpOpen(true),
    }),
    [],
  );
  const manager = useMemo(
    () =>
      new ShortcutManager(
        [
          {
            id: "palette",
            description: "Open the command palette",
            defaultKeys: "mod+k",
            run: () => control.open(),
          },
          { id: "search", description: "Search", defaultKeys: "/", run: () => control.open() },
          {
            id: "help",
            description: "Show keyboard shortcuts",
            defaultKeys: "?",
            run: control.openShortcuts,
          },
          { id: "go-home", description: "Go to the home page", defaultKeys: "g h", run: () => navigate("/") },
          {
            id: "go-services",
            description: "Go to services",
            defaultKeys: "g s",
            run: () => navigate("/services"),
          },
          {
            id: "go-account",
            description: "Go to my account",
            defaultKeys: "g a",
            run: () => navigate("/account"),
          },
        ],
        shortcutOverrides,
      ),
    [control, navigate, shortcutOverrides],
  );
  useEffect(() => manager.attach(), [manager]);
  const actions = useMemo(() => ({ "shell.show_shortcuts": control.openShortcuts }), [control]);

  return (
    <PaletteContext.Provider value={control}>
      <a className="skip-link" href="#main-content">
        {shellStrings.skip}
      </a>
      <header className="shell-header">
        <span className="shell-brand">{shellStrings.brand}</span>
        <div className="ds-stack ds-stack--row shell-header__slots">
          <SearchEntry />
          <AiEntry />
          <NotificationEntry />
          <HelpEntry />
          <IdentityMenu name={userName} onSignOut={onSignOut} onNavigate={(to) => navigate(to)} />
        </div>
      </header>
      <GlobalStatusBanner />
      <div className="shell-body">
        <ResponsiveNav collapsed={sidebarCollapsed} />
        <main id="main-content" tabIndex={-1} className="shell-main ds-reflow">
          <Breadcrumbs />
          <RegionBoundary resetKey={location.pathname}>{children ?? <Outlet />}</RegionBoundary>
          <RelatedLinks />
        </main>
      </div>
      <CommandPalette
        open={palette.open}
        initialQuery={palette.query}
        onOpenChange={(open) => setPalette((current) => ({ ...current, open }))}
        actions={actions}
      />
      <Dialog
        title={shellStrings.shortcutsTitle}
        open={helpOpen}
        onOpenChange={setHelpOpen}
        trigger={<span hidden />}
      >
        <dl className="shell-shortcuts">
          {manager.list().map(({ keys, action }) => (
            <div key={action.id}>
              <dt>
                <kbd>{keys}</kbd>
              </dt>
              <dd>{action.description}</dd>
            </div>
          ))}
        </dl>
      </Dialog>
    </PaletteContext.Provider>
  );
}
