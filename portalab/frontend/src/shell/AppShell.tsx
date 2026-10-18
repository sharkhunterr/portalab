import { type CSSProperties, type ReactNode, useEffect, useMemo, useState } from "react";
import { Outlet, useLocation, useNavigate, useNavigationType } from "react-router";
import { Dialog, Drawer } from "../design-system/components/Overlays";
import { NAV_DESKTOP, NAV_PHONE, NAV_TABLET } from "../design-system/themes/schema";
import { ExternalVisualsLoader } from "../design-system/visuals/ExternalVisualsLoader";
import { externalLook, useExternalRevision } from "../design-system/visuals/registry";
import { useWornLevelBadge } from "../features/community/profile/looks";
import { LevelUpMoment } from "../features/gamification/levelup/LevelUpMoment";
import { BoosterStageHost } from "../features/marketplace/boosters/StageHost";
import { ListenHost } from "../features/media/listen/ListenHost";
import { useListen } from "../features/media/listen/store";
import { PluginCorners } from "../features/plugins/slots/PluginSlot";
import { Breadcrumbs, RelatedLinks } from "./breadcrumbs/Breadcrumbs";
import { AppHeader } from "./header/AppHeader";
import { focusHeaderSearch, HeaderSearch, openFloatingSearch } from "./header/HeaderSearch";
import { ProfileCard } from "./header/ProfileCard";
import { useHeaderData } from "./header/useHeaderData";
import { BottomBar } from "./nav/BottomBar";
import { DeckNav, PlanisphereNav, SystemNav } from "./nav/CosmosNavs";
import { HubTabs } from "./nav/HubTabs";
import { useArrangement } from "./nav/NavFrame";
import { useNavigationView } from "./nav/NavigationProvider";
import { OrbitNav } from "./nav/OrbitNav";
import { PackNav, packNavLayout } from "./nav/PackNav";
import {
  ConsoleNav,
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
import {
  DpadNav,
  FeedSide,
  FeedTabs,
  MastheadNav,
  PlayerBar,
  PlayerLibrary,
  TaskbarNav,
} from "./nav/UniverseNavs";
import { CommandPalette } from "./palette/CommandPalette";
import { PaletteContext } from "./palette/PaletteContext";
import { RegionBoundary } from "./router/RouteBoundary";
import { isSafeMode } from "./safeMode";
import { ShortcutManager } from "./shortcuts/ShortcutManager";
import { AnnouncementBanner } from "./status/AnnouncementBanner";
import { GlobalStatusBanner } from "./status/GlobalStatusBanner";
import { MaintenanceBanner } from "./status/MaintenanceBanner";
import { SafeModeBanner } from "./status/SafeModeBanner";
import { useShellStrings } from "./strings";

/**
 * Persistent shell (spec 004 T017; 027 US1–US3): one environment for every module — the personal header,
 * the section navigation in the arrangement the theme chose for the device (sidebar, rail, top bar,
 * drawer, phone bottom bar, orbit bubble, dock, book tabs, launcher screen, terminal line, film reel, desktop
 * taskbar, social feed, music player, newspaper masthead; header on top
 * or as a footer bar), the global status banner,
 * breadcrumbs and the page outlet. Only the outlet changes on navigation, and a change of arrangement
 * never remounts it: the page keeps its state. Unknown to anonymous visitors (CD-025).
 */
const BUILTIN_NAVS = [...new Set([...NAV_DESKTOP, ...NAV_TABLET, ...NAV_PHONE])];

export interface AppShellProps {
  userName: string;
  onSignOut: () => void;
  shortcutOverrides?: Record<string, string>;
  sidebarCollapsed?: boolean;
  children?: ReactNode;
}

/** 028 (R16): the pages no imported interface restyles — their content keeps Portalab's own look. */
export const PROTECTED_PAGES = /^\/(admin|account|privacy)(\/|$)/;

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
  const listening = useListen().objectId !== null; // #20: the audiobook bar takes its place at the bottom
  useWornLevelBadge(Boolean(header.me)); // 027: the level badge look the member wears, everywhere
  const [menuOpen, setMenuOpen] = useState(false);
  // biome-ignore lint/correctness/useExhaustiveDependencies: close the menu panel on navigation
  useEffect(() => setMenuOpen(false), [location.pathname]);
  // a new page opens at its top (going back keeps where one was; an anchor keeps its target)
  const navigation = useNavigationType();
  // biome-ignore lint/correctness/useExhaustiveDependencies: on each new page only
  useEffect(() => {
    if (navigation === "POP" || location.hash) return;
    window.scrollTo({ top: 0, left: 0 });
    const main = document.getElementById("main-content");
    if (main) main.scrollTop = 0;
  }, [location.pathname]);
  const sections = view.sections;
  // issue 1: a navigation an imported pack brings (its own script, sandboxed) — never on a protected surface
  // (the administration keeps its own), and a built-in one takes over when it fails
  useExternalRevision();
  const packNavigation = externalLook("navigation", arrangement.nav);
  const [packFailed, setPackFailed] = useState<string | null>(null);
  // the administration, the account and its security, privacy: always Portalab's own (028, R16)
  const protectedSurface = PROTECTED_PAGES.test(location.pathname);
  const packNav =
    packNavigation && !protectedSurface && packFailed !== packNavigation.product ? packNavigation : null;
  const fallbackNav = arrangement.device === "phone" ? "bottom-bar" : "sidebar";
  // a navigation no pack brings (yet): the built-in one meanwhile — never a page without navigation
  const builtin = (BUILTIN_NAVS as readonly string[]).includes(arrangement.nav);
  const chosen = (packNavigation || !builtin) && !packNav ? fallbackNav : arrangement.nav;
  const nav = packNav ? "pack" : sidebarCollapsed && chosen === "sidebar" ? "rail" : chosen;
  const packLayout = packNav ? packNavLayout(packNav) : null;
  const drawerNav = nav === "drawer" || nav === "bottom-bar";
  const [palette, setPalette] = useState<{ open: boolean; query: string }>({ open: false, query: "" });
  const [helpOpen, setHelpOpen] = useState(false);
  const control = useMemo(
    () => ({
      // 027: the header's search answers first; the palette remains where the header has none
      open: (query = "") => {
        if (!focusHeaderSearch(query) && !openFloatingSearch(query)) setPalette({ open: true, query });
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
        data-pack-nav={packLayout?.position}
        style={packLayout ? ({ "--pack-nav-size": `${packLayout.size}px` } as CSSProperties) : undefined}
        data-device={arrangement.device}
        data-header-position={arrangement.headerPosition}
        data-listening={listening || undefined}
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
        <BoosterStageHost />
        <ListenHost />
        <AnnouncementBanner />
        <MaintenanceBanner />
        {isSafeMode() ? <SafeModeBanner /> : null}
        {nav === "topbar" ? (
          <nav aria-label={shellStrings.mainNav} className="shell-topnav">
            <NavContent variant="bar" />
          </nav>
        ) : null}
        {nav === "terminal" ? <TerminalNav sections={sections} /> : null}
        {nav === "reel" ? <ReelNav sections={sections} /> : null}
        {nav === "lights" ? <LightsNav sections={sections} /> : null}
        {nav === "vcr" ? <VcrNav sections={sections} /> : null}
        {nav === "masthead" ? <MastheadNav sections={sections} /> : null}
        {nav === "feed" ? <FeedTabs sections={sections} /> : null}
        <div className="shell-body">
          {nav === "tabs" ? <TabsNav sections={sections} /> : null}
          {nav === "feed" && arrangement.device !== "phone" ? <FeedSide sections={sections} /> : null}
          {nav === "player" && arrangement.device !== "phone" ? <PlayerLibrary sections={sections} /> : null}
          {nav === "sidebar" || nav === "rail" ? (
            <nav aria-label={shellStrings.mainNav} className="shell-side" data-variant={nav}>
              {nav === "sidebar" ? <ProfileCard data={header} /> : null}
              <NavContent variant={nav === "rail" ? "rail" : "list"} />
            </nav>
          ) : null}
          <main
            id="main-content"
            tabIndex={-1}
            className="shell-main ds-reflow"
            data-protected={protectedSurface ? "" : undefined}
          >
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
        {nav === "console" ? <ConsoleNav sections={sections} /> : null}
        {nav === "taskbar" ? <TaskbarNav sections={sections} /> : null}
        {nav === "dpad" ? <DpadNav sections={sections} /> : null}
        {nav === "planisphere" ? <PlanisphereNav sections={sections} /> : null}
        {nav === "system" ? <SystemNav sections={sections} /> : null}
        {packNav ? (
          <PackNav
            element={packNav}
            sections={sections}
            unread={header.unread}
            level={header.progression?.level ?? null}
            coins={header.progression?.coins ?? null}
            onFail={() => setPackFailed(packNav.product)}
          />
        ) : null}
        {nav === "deck" ? (
          <DeckNav sections={sections} progression={header.progression} unread={header.unread} />
        ) : null}
        {nav === "player" ? <PlayerBar sections={sections} library={arrangement.device === "phone"} /> : null}
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
      {/* #67: the header's search over the page, for the layouts whose header has none */}
      <HeaderSearch floating />
      {/* 029: safe mode loads nothing of any pack */}
      {isSafeMode() ? null : <ExternalVisualsLoader />}
      {/* 030: what plugins place in a corner of every screen (a messenger's button…) */}
      <PluginCorners />
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
