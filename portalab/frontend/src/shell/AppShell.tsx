import { type ReactNode, useEffect, useMemo, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router";
import { Dialog, Drawer } from "../design-system/components/Overlays";
import { useWornLevelBadge } from "../features/community/profile/looks";
import { LevelUpMoment } from "../features/gamification/levelup/LevelUpMoment";
import { Breadcrumbs, RelatedLinks } from "./breadcrumbs/Breadcrumbs";
import { AppHeader } from "./header/AppHeader";
import { focusHeaderSearch } from "./header/HeaderSearch";
import { ProfileCard } from "./header/ProfileCard";
import { useHeaderData } from "./header/useHeaderData";
import { BottomBar } from "./nav/BottomBar";
import { HubTabs } from "./nav/HubTabs";
import { useArrangement } from "./nav/NavFrame";
import { useNavigationView } from "./nav/NavigationProvider";
import { OrbitNav } from "./nav/OrbitNav";
import {
  DockNav,
  LauncherNav,
  LightsNav,
  ReelNav,
  SheetNav,
  TabsNav,
  TerminalNav,
  VcrNav,
} from "./nav/PrincipleNavs";
import { NavContent } from "./nav/SectionNav";
import { CommandPalette } from "./palette/CommandPalette";
import { PaletteContext } from "./palette/PaletteContext";
import { RegionBoundary } from "./router/RouteBoundary";
import { ShortcutManager } from "./shortcuts/ShortcutManager";
import { AnnouncementBanner } from "./status/AnnouncementBanner";
import { GlobalStatusBanner } from "./status/GlobalStatusBanner";
import { MaintenanceBanner } from "./status/MaintenanceBanner";
import { useShellStrings } from "./strings";

/**
 * Persistent shell (spec 004 T017; 027 US1–US3): one environment for every module — the personal header,
 * the section navigation in the arrangement the theme chose for the device (sidebar, rail, top bar,
 * drawer, phone bottom bar, orbit bubble, dock, book tabs, launcher screen, terminal line, film reel; header on top
 * or as a footer bar), the global status banner,
 * breadcrumbs and the page outlet. Only the outlet changes on navigation, and a change of arrangement
 * never remounts it: the page keeps its state. Unknown to anonymous visitors (CD-025).
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
  const arrangement = useArrangement();
  const { view } = useNavigationView();
  const header = useHeaderData();
  useWornLevelBadge(Boolean(header.me)); // 027: the level badge look the member wears, everywhere
  const [menuOpen, setMenuOpen] = useState(false);
  // biome-ignore lint/correctness/useExhaustiveDependencies: close the menu panel on navigation
  useEffect(() => setMenuOpen(false), [location.pathname]);
  const sections = view.sections;
  const nav = sidebarCollapsed && arrangement.nav === "sidebar" ? "rail" : arrangement.nav;
  const drawerNav = nav === "drawer" || nav === "bottom-bar";
  const [palette, setPalette] = useState<{ open: boolean; query: string }>({ open: false, query: "" });
  const [helpOpen, setHelpOpen] = useState(false);
  const control = useMemo(
    () => ({
      // 027: the header's search answers first; the palette remains where the header has none
      open: (query = "") => {
        if (!focusHeaderSearch(query)) setPalette({ open: true, query });
      },
      openShortcuts: () => setHelpOpen(true),
    }),
    [],
  );
  const manager = useMemo(
    () =>
      new ShortcutManager(
        [
          { id: "search", description: "Search", defaultKeys: "mod+k", run: () => control.open() },
          { id: "search-slash", description: "Search", defaultKeys: "/", run: () => control.open() },
          {
            id: "palette",
            description: "Open the command palette",
            defaultKeys: "mod+shift+k",
            run: () => setPalette({ open: true, query: "" }),
          },
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
      <div
        className="shell"
        data-nav={nav}
        data-device={arrangement.device}
        data-header-position={arrangement.headerPosition}
      >
        <AppHeader
          device={arrangement.device}
          data={header}
          fallbackName={userName}
          personal={view.personal}
          onNavigate={(to) => navigate(to)}
          onSignOut={onSignOut}
          onOpenNavigation={nav === "drawer" ? () => setMenuOpen(true) : undefined}
          bottomBar={nav === "bottom-bar"}
        />
        <GlobalStatusBanner />
        <LevelUpMoment />
        <AnnouncementBanner />
        <MaintenanceBanner />
        {nav === "topbar" ? (
          <nav aria-label={shellStrings.mainNav} className="shell-topnav">
            <NavContent variant="bar" />
          </nav>
        ) : null}
        {nav === "terminal" ? <TerminalNav sections={sections} /> : null}
        {nav === "reel" ? <ReelNav sections={sections} /> : null}
        {nav === "lights" ? <LightsNav sections={sections} /> : null}
        {nav === "vcr" ? <VcrNav sections={sections} /> : null}
        <div className="shell-body">
          {nav === "tabs" ? <TabsNav sections={sections} /> : null}
          {nav === "sidebar" || nav === "rail" ? (
            <nav aria-label={shellStrings.mainNav} className="shell-side" data-variant={nav}>
              {nav === "sidebar" ? <ProfileCard data={header} /> : null}
              <NavContent variant={nav === "rail" ? "rail" : "list"} />
            </nav>
          ) : null}
          <main id="main-content" tabIndex={-1} className="shell-main ds-reflow">
            <div className="shell-content">
              <Breadcrumbs />
              {nav === "terminal" ? null : <HubTabs />}
              <RegionBoundary resetKey={location.pathname}>{children ?? <Outlet />}</RegionBoundary>
              <RelatedLinks />
            </div>
          </main>
        </div>
        {nav === "bottom-bar" ? (
          <BottomBar unread={header.unread} menuOpen={menuOpen} onOpenMenu={() => setMenuOpen(true)} />
        ) : null}
        {nav === "orbit" ? <OrbitNav sections={sections} /> : null}
        {nav === "dock" ? <DockNav sections={sections} /> : null}
        {nav === "launcher" ? <LauncherNav sections={sections} /> : null}
        {nav === "sheet" ? <SheetNav sections={sections} /> : null}
        {drawerNav ? (
          <Drawer
            title={shellStrings.mainNav}
            open={menuOpen}
            onOpenChange={setMenuOpen}
            closeLabel={shellStrings.closeMenu}
            trigger={<span hidden />}
          >
            <ProfileCard
              data={header}
              personal={view.personal}
              onNavigate={() => setMenuOpen(false)}
              {...(arrangement.device === "phone" ? { onSignOut } : {})}
            />
            <nav aria-label={shellStrings.mainNav}>
              <NavContent onNavigate={() => setMenuOpen(false)} />
            </nav>
          </Drawer>
        ) : null}
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
