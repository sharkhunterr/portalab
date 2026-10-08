import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  type CSSProperties,
  type KeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  useEffect,
  useRef,
  useState,
} from "react";
import { NavLink, useLocation } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { Dialog } from "../../design-system/components/Overlays";
import { useShellStrings } from "../strings";
import type { NavSection } from "./NavigationProvider";
import { currentEntry, isHubSection, sectionEntries } from "./SectionNav";

/**
 * Navigation principles chosen by themes (027 R24, beyond the sidebar and the orbit): a floating **dock**,
 * book **tabs** on the edge, a game-like **launcher** screen, a **terminal** command line, a film
 * **reel** (the sections as frames of a strip, sprocket holes and all) and a string of **lights** (each
 * section painted on a wall under its bulb, the current one lit). Same
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

/** 027 Reel: the sections as the frames of a film strip under the header — the current one lit, a section
 * with several destinations unrolls them below; a scrolling strip on phones. */
export function ReelNav({ sections }: { sections: readonly NavSection[] }) {
  const strings = useShellStrings();
  const { current, isActive } = useCurrent(sections);
  const { open, setOpen, root } = useOpenSection();
  const section = sections.find((s) => s.key === open);
  return (
    <nav ref={root} className="shell-reel" aria-label={strings.mainNav}>
      {/* biome-ignore lint/a11y/noNoninteractiveElementInteractions: arrow keys move along the strip */}
      <ul className="shell-reel__strip" onKeyDown={(event) => moveFocus(event)}>
        {sections.map((s, index) => (
          <li key={s.key} style={{ "--i": index } as CSSProperties}>
            <SectionItem
              section={s}
              active={isActive(s)}
              open={open === s.key}
              onToggle={() => setOpen(open === s.key ? null : s.key)}
              className="shell-reel__frame"
            />
          </li>
        ))}
      </ul>
      {section ? (
        <div className="shell-reel__panel">
          <DestinationList section={section} currentKey={current?.key} onPick={() => setOpen(null)} />
        </div>
      ) : null}
    </nav>
  );
}

/** 027 Lights: the sections painted on a wall, each under a bulb of a string of Christmas lights — the
 * current one lit, the others blinking now and then; a section with several destinations opens below. */
export function LightsNav({ sections }: { sections: readonly NavSection[] }) {
  const strings = useShellStrings();
  const { current, isActive } = useCurrent(sections);
  const { open, setOpen, root } = useOpenSection();
  const section = sections.find((s) => s.key === open);
  return (
    <nav ref={root} className="shell-lights" aria-label={strings.mainNav}>
      {/* biome-ignore lint/a11y/noNoninteractiveElementInteractions: arrow keys move along the string */}
      <ul className="shell-lights__wall" onKeyDown={(event) => moveFocus(event)}>
        {sections.map((s, index) => (
          <li key={s.key} style={{ "--i": index } as CSSProperties}>
            <span className="shell-lights__bulb" aria-hidden="true" />
            <SectionItem
              section={s}
              active={isActive(s)}
              open={open === s.key}
              onToggle={() => setOpen(open === s.key ? null : s.key)}
              className="shell-lights__item"
            />
          </li>
        ))}
      </ul>
      {section ? (
        <div className="shell-lights__panel">
          <DestinationList section={section} currentKey={current?.key} onPick={() => setOpen(null)} />
        </div>
      ) : null}
    </nav>
  );
}

/** The route a section leads to first. */
function firstRoute(section: NavSection): string {
  return destinationsOf(section, undefined)[0]?.route ?? "/";
}

/** A tape counter running since the page opened (h:mm:ss), like a VCR's display. */
function TapeCounter() {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    <span className="shell-vcr__counter" aria-hidden="true">
      {Math.floor(seconds / 3600)}:{pad(Math.floor(seconds / 60) % 60)}:{pad(seconds % 60)}
    </span>
  );
}

/**
 * 027 VCR: a video recorder's display under the header — PLAY, the current section as a numbered channel,
 * ◀◀ and ▶▶ to zap to the previous or next section, a tape counter; MENU opens the blue on-screen menu
 * with every section as a channel and its pages under it.
 */
export function VcrNav({ sections }: { sections: readonly NavSection[] }) {
  const strings = useShellStrings();
  const { current, isActive, pathname } = useCurrent(sections);
  const [open, setOpen] = useState(false);
  // biome-ignore lint/correctness/useExhaustiveDependencies: close on navigation
  useEffect(() => setOpen(false), [pathname]);
  if (!sections.length) return null;
  const index = Math.max(0, sections.findIndex(isActive));
  const here = sections[index] as NavSection;
  const previous = sections[(index - 1 + sections.length) % sections.length] as NavSection;
  const next = sections[(index + 1) % sections.length] as NavSection;
  const channel = (i: number) => `CH ${String(i + 1).padStart(2, "0")}`;
  return (
    <nav className="shell-vcr" aria-label={strings.mainNav}>
      <div className="shell-vcr__deck">
        <span className="shell-vcr__play" aria-hidden="true">
          PLAY ▶
        </span>
        <NavLink
          to={firstRoute(previous)}
          end
          className="shell-vcr__zap"
          aria-label={`${strings.previousSection} — ${strings.label(previous.label_key)}`}
        >
          ◀◀
        </NavLink>
        <span className="shell-vcr__channel">
          <span className="shell-vcr__number">{channel(index)}</span>
          <span className="shell-vcr__name">{strings.label(here.label_key)}</span>
        </span>
        <NavLink
          to={firstRoute(next)}
          end
          className="shell-vcr__zap"
          aria-label={`${strings.nextSection} — ${strings.label(next.label_key)}`}
        >
          ▶▶
        </NavLink>
        <TapeCounter />
        <Dialog
          open={open}
          onOpenChange={setOpen}
          size="full"
          title={strings.mainNav}
          closeLabel={strings.closeMenu}
          trigger={
            <button type="button" className="shell-vcr__menu" aria-expanded={open}>
              {strings.menu}
            </button>
          }
        >
          <ol className="shell-vcr__osd">
            {sections.map((section, i) => {
              const destinations = destinationsOf(section, current?.key);
              return (
                <li key={section.key} data-active={isActive(section) ? "true" : undefined}>
                  <NavLink to={firstRoute(section)} end className="shell-vcr__entry">
                    <span className="shell-vcr__number">{channel(i)}</span>
                    {strings.label(section.label_key)}
                  </NavLink>
                  {destinations.length > 1 ? (
                    <DestinationList
                      section={section}
                      currentKey={current?.key}
                      className="shell-vcr__pages"
                    />
                  ) : null}
                </li>
              );
            })}
          </ol>
        </Dialog>
      </div>
    </nav>
  );
}

/** One app icon of the sheet: a link, or a folder button when the section has several destinations. */
function AppIcon({
  label,
  icon,
  index,
  active,
  to,
  onOpen,
}: {
  label: string;
  icon: string | null | undefined;
  index: number;
  active: boolean;
  to?: string;
  onOpen?: () => void;
}) {
  const body = (
    <>
      <span className="shell-sheet__app-icon" aria-hidden="true">
        <Icon name={icon ?? "dashboard"} size={26} />
      </span>
      <span className="shell-sheet__app-label">{label}</span>
    </>
  );
  const style = { "--i": index } as CSSProperties;
  if (onOpen) {
    return (
      <button
        type="button"
        className="shell-sheet__app"
        data-folder
        data-active={active ? "true" : undefined}
        style={style}
        onClick={onOpen}
      >
        {body}
      </button>
    );
  }
  return (
    <NavLink
      to={to ?? "/"}
      end
      className="shell-sheet__app"
      data-active={active ? "true" : undefined}
      aria-current={active ? "page" : undefined}
      style={style}
    >
      {body}
    </NavLink>
  );
}

/**
 * 027 Sheet: a phone's navigation on every screen — a bottom bar with a few shortcuts either side of a big
 * round button that slides a sheet up from the bottom: every section as an app icon; a section with
 * several pages opens like a folder (Back returns). Escape, the backdrop, or dragging the handle down
 * closes it.
 */
export function SheetNav({ sections }: { sections: readonly NavSection[] }) {
  const strings = useShellStrings();
  const { current, isActive, pathname } = useCurrent(sections);
  const [open, setOpen] = useState(false);
  const [folder, setFolder] = useState<string | null>(null);
  const [drag, setDrag] = useState(0);
  const start = useRef<number | null>(null);
  // biome-ignore lint/correctness/useExhaustiveDependencies: close on navigation
  useEffect(() => {
    setOpen(false);
    setFolder(null);
  }, [pathname]);
  const opened = sections.find((s) => s.key === folder);
  const shortcuts = sections.slice(0, 4);
  const shortcut = (s: NavSection) => {
    const active = isActive(s);
    const label = strings.label(s.label_key);
    return (
      <li key={s.key}>
        <NavLink
          to={firstRoute(s)}
          end={firstRoute(s) === "/"}
          className="shell-sheet__shortcut"
          data-nav-item
          data-active={active ? "true" : undefined}
          aria-current={active ? "page" : undefined}
          title={label}
        >
          <Icon name={s.icon ?? destinationsOf(s, undefined)[0]?.icon} size={22} />
          <span className="shell-sheet__shortcut-label">{label}</span>
        </NavLink>
      </li>
    );
  };
  const onOpenChange = (next: boolean) => {
    setOpen(next);
    if (!next) setFolder(null);
  };
  const onPointerDown = (event: ReactPointerEvent<HTMLElement>) => {
    start.current = event.clientY;
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const onPointerMove = (event: ReactPointerEvent<HTMLElement>) => {
    if (start.current !== null) setDrag(Math.max(0, event.clientY - start.current));
  };
  const onPointerUp = () => {
    if (drag > 90) onOpenChange(false);
    start.current = null;
    setDrag(0);
  };
  return (
    <nav className="shell-sheet" aria-label={strings.mainNav}>
      {/* biome-ignore lint/a11y/noNoninteractiveElementInteractions: arrow keys move along the bar */}
      <ul className="shell-sheet__bar" onKeyDown={(event) => moveFocus(event)}>
        {shortcuts.slice(0, 2).map(shortcut)}
        <li className="shell-sheet__center">
          <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
            <DialogPrimitive.Trigger className="shell-sheet__fab" data-nav-item aria-label={strings.sections}>
              <Icon name={open ? "close" : "apps"} size={26} />
            </DialogPrimitive.Trigger>
            <DialogPrimitive.Portal>
              <DialogPrimitive.Overlay className="shell-sheet__backdrop" />
              <DialogPrimitive.Content
                className="shell-sheet__panel"
                aria-describedby={undefined}
                data-dragging={drag ? "true" : undefined}
                style={{ "--drag": `${drag}px` } as CSSProperties}
              >
                <span
                  className="shell-sheet__handle"
                  aria-hidden="true"
                  onPointerDown={onPointerDown}
                  onPointerMove={onPointerMove}
                  onPointerUp={onPointerUp}
                  onPointerCancel={onPointerUp}
                />
                <div className="shell-sheet__head">
                  {opened ? (
                    <button type="button" className="shell-sheet__back" onClick={() => setFolder(null)}>
                      <Icon name="chevron-left" size={18} />
                      {strings.back}
                    </button>
                  ) : null}
                  <DialogPrimitive.Title className="shell-sheet__title">
                    {opened ? strings.label(opened.label_key) : strings.sections}
                  </DialogPrimitive.Title>
                  <DialogPrimitive.Close className="shell-sheet__close" aria-label={strings.closeMenu}>
                    <Icon name="close" size={18} />
                  </DialogPrimitive.Close>
                </div>
                <ul className="shell-sheet__apps" data-folder={opened ? "true" : undefined}>
                  {opened
                    ? destinationsOf(opened, current?.key).map((page, i) => (
                        <li key={page.key}>
                          <AppIcon
                            label={strings.label(page.label_key)}
                            icon={page.icon}
                            index={i}
                            active={page.active}
                            to={page.route}
                          />
                        </li>
                      ))
                    : sections.map((s, i) => {
                        const destinations = destinationsOf(s, current?.key);
                        return (
                          <li key={s.key}>
                            <AppIcon
                              label={strings.label(s.label_key)}
                              icon={s.icon ?? destinations[0]?.icon}
                              index={i}
                              active={isActive(s)}
                              {...(destinations.length > 1
                                ? { onOpen: () => setFolder(s.key) }
                                : { to: destinations[0]?.route ?? "/" })}
                            />
                          </li>
                        );
                      })}
                </ul>
              </DialogPrimitive.Content>
            </DialogPrimitive.Portal>
          </DialogPrimitive.Root>
        </li>
        {shortcuts.slice(2, 4).map(shortcut)}
      </ul>
    </nav>
  );
}

/** The ship's clock: date and time, ticking each second (in the theme's monospaced figures). */
function ShipClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    <span className="shell-console__clock" aria-hidden="true">
      {now.getFullYear()}.{pad(now.getMonth() + 1)}.{pad(now.getDate())} · {pad(now.getHours())}:
      {pad(now.getMinutes())}:{pad(now.getSeconds())}
    </span>
  );
}

/**
 * 027 console (Nostromo): a ship's console docked at the bottom — a status line (MU/TH/UR, the section, NOMINAL,
 * the ship's clock and a heartbeat trace), then the sections as icons, the current one opened out with its
 * name in an amber frame; a section with pages opens them above, like the dock.
 */
export function ConsoleNav({ sections }: { sections: readonly NavSection[] }) {
  const strings = useShellStrings();
  const { current, isActive } = useCurrent(sections);
  const { open, setOpen, root } = useOpenSection();
  const section = sections.find((s) => s.key === open);
  const here = sections.find(isActive);
  return (
    <nav ref={root} className="shell-dock shell-console" aria-label={strings.mainNav}>
      {section ? (
        <div className="shell-dock__panel shell-console__panel">
          <p className="shell-dock__title">{strings.label(section.label_key)}</p>
          <DestinationList section={section} currentKey={current?.key} />
        </div>
      ) : null}
      <p className="shell-console__status" aria-hidden="true">
        <span className="shell-console__lamp" />
        <span>MU/TH/UR 6000</span>
        <span className="shell-console__sep">·</span>
        <span className="shell-console__here">{here ? strings.label(here.label_key) : "—"}</span>
        <span className="shell-console__sep">·</span>
        <span>NOMINAL</span>
        <ShipClock />
        <svg
          className="shell-console__ecg"
          viewBox="0 0 120 24"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path d="M0 12 H34 L39 12 L42 4 L46 20 L50 2 L54 16 L57 12 H86 L90 9 L93 12 H120" />
        </svg>
      </p>
      {/* biome-ignore lint/a11y/noNoninteractiveElementInteractions: arrow keys move along the console */}
      <ul className="shell-dock__bar shell-console__bar" onKeyDown={(event) => moveFocus(event)}>
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
