import { type CSSProperties, type KeyboardEvent, useEffect, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { Dialog } from "../../design-system/components/Overlays";
import { useShellStrings } from "../strings";
import type { NavSection } from "./NavigationProvider";
import { currentEntry, isHubSection, sectionEntries } from "./SectionNav";

/**
 * Navigation principles chosen by themes (027 R24, beyond the sidebar and the orbit): a floating **dock**,
 * book **tabs** on the edge, a game-like **launcher** screen and a **terminal** command line. Same
 * destinations as every variant (the server-filtered sections); a member section opens on its first page
 * (its pages are hub tabs), Administration lists its topics. Keyboard: links and buttons in order, arrows
 * move along a bar, Escape closes what is open. Each one works on phones, tablets and desktops.
 */
export interface Destination {
  key: string;
  label_key: string;
  icon: string | null | undefined;
  route: string;
  active: boolean;
}

/** Where a section leads: its pages (member hub) or its topics (Administration). */
export function destinationsOf(section: NavSection, currentKey: string | undefined): Destination[] {
  if (section.audience === "administration" && section.topics.length) {
    return [
      ...section.entries.map((entry) => ({
        key: entry.key,
        label_key: entry.label_key,
        icon: entry.icon,
        route: entry.route ?? "/",
        active: entry.key === currentKey,
      })),
      ...section.topics.map((topic) => ({
        key: topic.key,
        label_key: topic.label_key,
        icon: topic.icon,
        route: topic.route ?? topic.entries[0]?.route ?? "/",
        active: topic.entries.some((entry) => entry.key === currentKey),
      })),
    ];
  }
  return sectionEntries(section).map((entry) => ({
    key: entry.key,
    label_key: entry.label_key,
    icon: entry.icon,
    route: entry.route ?? "/",
    active: entry.key === currentKey,
  }));
}

/** A section is one link (direct or member hub) or opens a list (Administration, plain sections). */
function opensList(section: NavSection): boolean {
  return !section.direct && !isHubSection(section) && destinationsOf(section, undefined).length > 1;
}

function useCurrent(sections: readonly NavSection[]) {
  const location = useLocation();
  const current = currentEntry(sections, location.pathname);
  const isActive = (section: NavSection) => sectionEntries(section).some((e) => e.key === current?.key);
  return { current, isActive, pathname: location.pathname };
}

/** Arrow keys move between the items of a bar (focusable children with ``data-nav-item``). */
function moveFocus(event: KeyboardEvent<HTMLElement>, vertical = false) {
  const next = vertical ? ["ArrowDown"] : ["ArrowRight"];
  const previous = vertical ? ["ArrowUp"] : ["ArrowLeft"];
  if (![...next, ...previous].includes(event.key)) return;
  const items = Array.from(event.currentTarget.querySelectorAll<HTMLElement>("[data-nav-item]"));
  const index = items.indexOf(document.activeElement as HTMLElement);
  if (index < 0) return;
  event.preventDefault();
  const step = next.includes(event.key) ? 1 : -1;
  items[(index + step + items.length) % items.length]?.focus();
}

function DestinationList({
  section,
  currentKey,
  onPick,
  className = "shell-entries",
}: {
  section: NavSection;
  currentKey: string | undefined;
  onPick?: () => void;
  className?: string;
}) {
  const strings = useShellStrings();
  return (
    <ul className={className}>
      {destinationsOf(section, currentKey).map((destination) => (
        <li key={destination.key}>
          <NavLink
            to={destination.route}
            end
            className="shell-entry"
            aria-current={destination.active ? "page" : undefined}
            onClick={onPick}
          >
            {destination.icon ? <Icon name={destination.icon} size={16} /> : null}
            {strings.label(destination.label_key)}
          </NavLink>
        </li>
      ))}
    </ul>
  );
}

/** A section as one item of a bar: a link, or a button opening its list (``aria-expanded``). */
function SectionItem({
  section,
  active,
  open,
  onToggle,
  className,
  showLabel = true,
}: {
  section: NavSection;
  active: boolean;
  open: boolean;
  onToggle: () => void;
  className: string;
  showLabel?: boolean;
}) {
  const strings = useShellStrings();
  const label = strings.label(section.label_key);
  const first = destinationsOf(section, undefined)[0];
  const body = (
    <>
      <span className={`${className}-icon`}>
        <Icon name={section.icon ?? first?.icon} />
      </span>
      <span className={`${className}-label`}>{label}</span>
    </>
  );
  if (!opensList(section)) {
    return (
      <NavLink
        to={first?.route ?? "/"}
        end={first?.route === "/"}
        className={className}
        data-nav-item
        data-active={active ? "true" : undefined}
        aria-current={active ? "page" : undefined}
        aria-label={showLabel ? undefined : label}
        title={label}
      >
        {body}
      </NavLink>
    );
  }
  return (
    <button
      type="button"
      className={className}
      data-nav-item
      data-active={active ? "true" : undefined}
      aria-expanded={open}
      aria-label={showLabel ? undefined : label}
      title={label}
      onClick={onToggle}
    >
      {body}
    </button>
  );
}

/** One open list at a time, closed on navigation, Escape or a click outside. */
function useOpenSection() {
  const location = useLocation();
  const [open, setOpen] = useState<string | null>(null);
  const root = useRef<HTMLElement>(null);
  // biome-ignore lint/correctness/useExhaustiveDependencies: close on navigation
  useEffect(() => setOpen(null), [location.pathname]);
  useEffect(() => {
    if (!open) return;
    const away = (event: PointerEvent) => {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(null);
    };
    const onEscape = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") setOpen(null);
    };
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", onEscape);
    return () => {
      document.removeEventListener("pointerdown", away);
      document.removeEventListener("keydown", onEscape);
    };
  }, [open]);
  return { open, setOpen, root };
}

/** Dock: a floating bar of sections at the bottom; hovering grows them, a list opens above the dock. */
export function DockNav({ sections }: { sections: readonly NavSection[] }) {
  const strings = useShellStrings();
  const { current, isActive } = useCurrent(sections);
  const { open, setOpen, root } = useOpenSection();
  const section = sections.find((s) => s.key === open);
  return (
    <nav ref={root} className="shell-dock" aria-label={strings.mainNav}>
      {section ? (
        <div className="shell-dock__panel">
          <p className="shell-dock__title">{strings.label(section.label_key)}</p>
          <DestinationList section={section} currentKey={current?.key} />
        </div>
      ) : null}
      {/* biome-ignore lint/a11y/noNoninteractiveElementInteractions: arrow keys move along the dock */}
      <ul className="shell-dock__bar" onKeyDown={(event) => moveFocus(event)}>
        {sections.map((s) => (
          <li key={s.key}>
            <SectionItem
              section={s}
              active={isActive(s)}
              open={open === s.key}
              onToggle={() => setOpen(open === s.key ? null : s.key)}
              className="shell-dock__item"
            />
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** Tabs: sections as bookmarks on the edge of the page (a scrolling strip on phones). */
export function TabsNav({ sections }: { sections: readonly NavSection[] }) {
  const strings = useShellStrings();
  const { current, isActive } = useCurrent(sections);
  const { open, setOpen, root } = useOpenSection();
  const section = sections.find((s) => s.key === open);
  return (
    <nav ref={root} className="shell-tabs" aria-label={strings.mainNav}>
      {/* biome-ignore lint/a11y/noNoninteractiveElementInteractions: arrow keys move between bookmarks */}
      <ul className="shell-tabs__list" onKeyDown={(event) => moveFocus(event, true)}>
        {sections.map((s, index) => (
          <li key={s.key} style={{ "--i": index } as CSSProperties}>
            <SectionItem
              section={s}
              active={isActive(s)}
              open={open === s.key}
              onToggle={() => setOpen(open === s.key ? null : s.key)}
              className="shell-tabs__item"
            />
          </li>
        ))}
      </ul>
      {section ? (
        <div className="shell-tabs__panel">
          <p className="shell-dock__title">{strings.label(section.label_key)}</p>
          <DestinationList section={section} currentKey={current?.key} onPick={() => setOpen(null)} />
        </div>
      ) : null}
    </nav>
  );
}

/** Launcher: a « start » button opening a full-screen menu of tiles, like a game's main menu. */
export function LauncherNav({ sections }: { sections: readonly NavSection[] }) {
  const strings = useShellStrings();
  const { current, isActive, pathname } = useCurrent(sections);
  const [open, setOpen] = useState(false);
  // biome-ignore lint/correctness/useExhaustiveDependencies: close on navigation
  useEffect(() => setOpen(false), [pathname]);
  const here = sections.find(isActive);
  return (
    <div className="shell-launcher">
      <Dialog
        open={open}
        onOpenChange={setOpen}
        size="full"
        title={strings.mainNav}
        closeLabel={strings.closeMenu}
        trigger={
          <button type="button" className="shell-launcher__start" aria-expanded={open}>
            <Icon name="dashboard" size={22} />
            <span>{strings.menu}</span>
            {here ? <span className="shell-launcher__here">{strings.label(here.label_key)}</span> : null}
          </button>
        }
      >
        <ul className="shell-launcher__grid">
          {sections.map((section, index) => {
            const destinations = destinationsOf(section, current?.key);
            const first = destinations[0];
            return (
              <li
                key={section.key}
                className="shell-launcher__tile"
                data-active={isActive(section) ? "true" : undefined}
                style={{ "--i": index } as CSSProperties}
              >
                <NavLink to={first?.route ?? "/"} end className="shell-launcher__head">
                  <span className="shell-launcher__icon">
                    <Icon name={section.icon ?? first?.icon} size={30} />
                  </span>
                  <span>{strings.label(section.label_key)}</span>
                </NavLink>
                {destinations.length > 1 ? (
                  <DestinationList
                    section={section}
                    currentKey={current?.key}
                    className="shell-launcher__pages"
                  />
                ) : null}
              </li>
            );
          })}
        </ul>
      </Dialog>
    </div>
  );
}

/** Terminal: the sections as commands on a prompt line, the current section's pages as sub-commands. */
export function TerminalNav({ sections }: { sections: readonly NavSection[] }) {
  const strings = useShellStrings();
  const { current, isActive } = useCurrent(sections);
  const here = sections.find(isActive);
  const pages = here ? destinationsOf(here, current?.key) : [];
  const slug = (key: string) =>
    strings
      .label(key)
      .toLowerCase()
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "");
  return (
    <nav className="shell-terminal" aria-label={strings.mainNav}>
      {/* biome-ignore lint/a11y/noNoninteractiveElementInteractions: arrow keys move between commands */}
      <ul className="shell-terminal__line" onKeyDown={(event) => moveFocus(event)}>
        <li className="shell-terminal__prompt" aria-hidden="true">
          ~/{here ? slug(here.label_key) : ""} $
        </li>
        {sections.map((s) => {
          const first = destinationsOf(s, undefined)[0];
          const active = isActive(s);
          return (
            <li key={s.key}>
              <NavLink
                to={first?.route ?? "/"}
                end={first?.route === "/"}
                className="shell-terminal__command"
                data-nav-item
                data-active={active ? "true" : undefined}
                aria-current={active ? "true" : undefined}
              >
                {slug(s.label_key)}
              </NavLink>
            </li>
          );
        })}
      </ul>
      {pages.length > 1 ? (
        <ul className="shell-terminal__line shell-terminal__line--sub">
          <li className="shell-terminal__prompt" aria-hidden="true">
            └─
          </li>
          {pages.map((page) => (
            <li key={page.key}>
              <NavLink
                to={page.route}
                end
                className="shell-terminal__command"
                data-active={page.active ? "true" : undefined}
                aria-current={page.active ? "page" : undefined}
              >
                {slug(page.label_key)}
              </NavLink>
            </li>
          ))}
        </ul>
      ) : null}
    </nav>
  );
}
