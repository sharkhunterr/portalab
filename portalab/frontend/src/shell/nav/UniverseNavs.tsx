import { type CSSProperties, useEffect, useMemo, useState } from "react";
import { NavLink, useNavigate } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { useShellStrings } from "../strings";
import type { NavSection } from "./NavigationProvider";
import {
  DestinationList,
  destinationsOf,
  moveFocus,
  opensList,
  SectionItem,
  useCurrent,
  useOpenSection,
} from "./PrincipleNavs";

/**
 * #89: navigations of their own for the universes — a desktop's **taskbar** (a Start button opening its
 * menu, the sections as tasks, a clock in the tray), a social network's **feed** (the sections as tabs in
 * the middle, the current one's pages and the other sections as shortcuts on the left), a music app's
 * **player** (the sections as playlists in a library on the left, a « now playing » bar at the bottom to go
 * to the previous or next page, or a random one) and a newspaper's **masthead** (its title, the date and
 * the sections as the paper's columns). Same destinations as every navigation; keyboard and phones too.
 */

function Clock({ seconds = false }: { seconds?: boolean }) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), seconds ? 1000 : 15000);
    return () => window.clearInterval(timer);
  }, [seconds]);
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    <time dateTime={now.toISOString()}>
      {pad(now.getHours())}:{pad(now.getMinutes())}
    </time>
  );
}

/** The panel a section opens (its pages), above or below its bar. */
function SectionPanel({
  section,
  currentKey,
  className,
}: {
  section: NavSection | undefined;
  currentKey: string | undefined;
  className: string;
}) {
  const strings = useShellStrings();
  if (!section) return null;
  return (
    <div className={className}>
      <p className="shell-dock__title">{strings.label(section.label_key)}</p>
      <DestinationList section={section} currentKey={currentKey} />
    </div>
  );
}

/** Taskbar: a Start button and its two-column menu, the sections as tasks, a clock in the tray. */
export function TaskbarNav({ sections }: { sections: readonly NavSection[] }) {
  const strings = useShellStrings();
  const t = useT();
  const { current, isActive } = useCurrent(sections);
  const { open, setOpen, root } = useOpenSection();
  const here = sections.find(isActive);
  const [pointed, setPointed] = useState<string | null>(null);
  const shown = sections.find((s) => s.key === (pointed ?? here?.key)) ?? sections[0];
  const section = sections.find((s) => s.key === open);
  return (
    <nav ref={root} className="shell-taskbar" aria-label={strings.mainNav}>
      {open === "start" ? (
        <div className="shell-taskbar__menu">
          <p className="shell-taskbar__menu-title">{t("shell:taskbar.menu")}</p>
          <div className="shell-taskbar__columns">
            {/* biome-ignore lint/a11y/noNoninteractiveElementInteractions: arrow keys move in the menu */}
            <ul className="shell-taskbar__sections" onKeyDown={(event) => moveFocus(event, true)}>
              {sections.map((s) => (
                <li key={s.key}>
                  <button
                    type="button"
                    data-nav-item
                    data-active={s.key === shown?.key || undefined}
                    onPointerEnter={() => setPointed(s.key)}
                    onFocus={() => setPointed(s.key)}
                    onClick={() => setPointed(s.key)}
                  >
                    <Icon name={s.icon ?? destinationsOf(s, undefined)[0]?.icon ?? "apps"} size={22} />
                    {strings.label(s.label_key)}
                  </button>
                </li>
              ))}
            </ul>
            {shown ? (
              <div className="shell-taskbar__pages">
                <p className="shell-taskbar__pages-title">{strings.label(shown.label_key)}</p>
                <DestinationList section={shown} currentKey={current?.key} onPick={() => setOpen(null)} />
              </div>
            ) : null}
          </div>
        </div>
      ) : (
        <SectionPanel section={section} currentKey={current?.key} className="shell-taskbar__panel" />
      )}
      <div className="shell-taskbar__bar">
        <button
          type="button"
          className="shell-taskbar__start"
          aria-expanded={open === "start"}
          onClick={() => setOpen(open === "start" ? null : "start")}
        >
          <Icon name="apps" size={18} />
          <span>{t("shell:taskbar.start")}</span>
        </button>
        {/* biome-ignore lint/a11y/noNoninteractiveElementInteractions: arrow keys move along the taskbar */}
        <ul className="shell-taskbar__tasks" onKeyDown={(event) => moveFocus(event)}>
          {sections.map((s) => (
            <li key={s.key}>
              <SectionItem
                section={s}
                active={isActive(s)}
                open={open === s.key}
                onToggle={() => setOpen(open === s.key ? null : s.key)}
                className="shell-taskbar__task"
              />
            </li>
          ))}
        </ul>
        <span className="shell-taskbar__tray">
          <Icon name="volume" size={14} />
          <Clock />
        </span>
      </div>
    </nav>
  );
}

/** Feed: the sections as icon tabs in the middle, under the header. */
export function FeedTabs({ sections }: { sections: readonly NavSection[] }) {
  const strings = useShellStrings();
  const { current, isActive } = useCurrent(sections);
  const { open, setOpen, root } = useOpenSection();
  const section = sections.find((s) => s.key === open);
  return (
    <nav ref={root} className="shell-feed" aria-label={strings.mainNav}>
      {/* biome-ignore lint/a11y/noNoninteractiveElementInteractions: arrow keys move along the tabs */}
      <ul className="shell-feed__tabs" onKeyDown={(event) => moveFocus(event)}>
        {sections.map((s) => (
          <li key={s.key}>
            <SectionItem
              section={s}
              active={isActive(s)}
              open={open === s.key}
              onToggle={() => setOpen(open === s.key ? null : s.key)}
              className="shell-feed__tab"
            />
          </li>
        ))}
      </ul>
      <SectionPanel section={section} currentKey={current?.key} className="shell-feed__panel" />
    </nav>
  );
}

/** Feed: on the left, the current section's pages, then the other sections as shortcuts. */
export function FeedSide({ sections }: { sections: readonly NavSection[] }) {
  const strings = useShellStrings();
  const t = useT();
  const { current, isActive } = useCurrent(sections);
  const here = sections.find(isActive) ?? sections[0];
  return (
    <aside className="shell-feed-side" aria-label={t("shell:feed.shortcuts")}>
      {here ? (
        <>
          <p className="shell-feed-side__title">{strings.label(here.label_key)}</p>
          <DestinationList
            section={here}
            currentKey={current?.key}
            className="shell-entries shell-feed-side__list"
          />
        </>
      ) : null}
      <p className="shell-feed-side__title">{t("shell:feed.shortcuts")}</p>
      <ul className="shell-entries shell-feed-side__list">
        {sections
          .filter((s) => s.key !== here?.key)
          .map((s) => {
            const first = destinationsOf(s, undefined)[0];
            return (
              <li key={s.key}>
                <NavLink to={first?.route ?? "/"} end={first?.route === "/"} className="shell-entry">
                  <span className="shell-feed-side__icon">
                    <Icon name={s.icon ?? first?.icon ?? "apps"} size={16} />
                  </span>
                  {strings.label(s.label_key)}
                </NavLink>
              </li>
            );
          })}
      </ul>
    </aside>
  );
}

/** Every page in order, across the sections (the player's previous and next). */
function useTrackList(sections: readonly NavSection[]) {
  return useMemo(
    () =>
      sections.flatMap((section) =>
        destinationsOf(section, undefined).map((destination) => ({ section, destination })),
      ),
    [sections],
  );
}

/** Player: the sections as playlists in a library on the left (desktop and tablet). */
export function PlayerLibrary({ sections }: { sections: readonly NavSection[] }) {
  const strings = useShellStrings();
  const t = useT();
  const { current, isActive } = useCurrent(sections);
  const { open, setOpen } = useOpenSection();
  return (
    <aside className="shell-player-library" aria-label={strings.mainNav}>
      <p className="shell-player-library__title">
        <Icon name="library" size={18} />
        {t("shell:player.library")}
      </p>
      <ul className="shell-player-library__list">
        {sections.map((s, index) => {
          const pages = destinationsOf(s, current?.key);
          const first = pages[0];
          const expanded = open === s.key || (isActive(s) && pages.length > 1 && open === null);
          return (
            <li key={s.key} data-active={isActive(s) || undefined}>
              <div className="shell-player-library__row">
                <NavLink
                  to={first?.route ?? "/"}
                  end={first?.route === "/"}
                  className="shell-player-library__playlist"
                  style={{ "--hue": (index * 47) % 360 } as CSSProperties}
                >
                  <span className="shell-player-library__cover">
                    <Icon name={s.icon ?? first?.icon ?? "music"} size={18} />
                  </span>
                  <span className="shell-player-library__text">
                    <strong>{strings.label(s.label_key)}</strong>
                    <small>{t("shell:player.pages", { count: pages.length })}</small>
                  </span>
                </NavLink>
                {opensList(s) || pages.length > 1 ? (
                  <button
                    type="button"
                    className="shell-player-library__more"
                    aria-expanded={expanded}
                    aria-label={strings.label(s.label_key)}
                    onClick={() => setOpen(expanded ? "" : s.key)}
                  >
                    <Icon name={expanded ? "chevron-down" : "chevron-right"} size={16} />
                  </button>
                ) : null}
              </div>
              {expanded ? (
                <DestinationList
                  section={s}
                  currentKey={current?.key}
                  className="shell-entries shell-player-library__tracks"
                />
              ) : null}
            </li>
          );
        })}
      </ul>
    </aside>
  );
}

/** Player: the « now playing » bar — the page as the track, previous / shuffle / next, and how far down
 * the page one has scrolled as its progress; ``library`` (phones) adds a button opening every playlist. */
export function PlayerBar({
  sections,
  library = false,
}: {
  sections: readonly NavSection[];
  library?: boolean;
}) {
  const strings = useShellStrings();
  const t = useT();
  const navigate = useNavigate();
  const tracks = useTrackList(sections);
  const { current, isActive } = useCurrent(sections);
  const { open, setOpen, root } = useOpenSection();
  const here = sections.find(isActive);
  const index = tracks.findIndex((track) => track.destination.key === current?.key);
  const [progress, setProgress] = useState(0);
  useEffect(() => {
    const update = () => {
      const max = document.documentElement.scrollHeight - window.innerHeight;
      setProgress(max > 0 ? Math.min(1, window.scrollY / max) : 0);
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    return () => window.removeEventListener("scroll", update);
  }, []);
  const go = (step: number) => {
    if (!tracks.length) return;
    const next = tracks[(Math.max(index, 0) + step + tracks.length) % tracks.length];
    if (next) navigate(next.destination.route);
  };
  const shuffle = () => {
    const pick = tracks[Math.floor(Math.random() * tracks.length)];
    if (pick) navigate(pick.destination.route);
  };
  const page = index >= 0 ? tracks[index]?.destination : undefined;
  return (
    <nav ref={root} className="shell-player" aria-label={t("shell:player.nowPlaying")}>
      {open === "library" ? (
        <div className="shell-player__sheet">
          <p className="shell-dock__title">{t("shell:player.library")}</p>
          {sections.map((s) => (
            <div key={s.key} className="shell-player__sheet-group">
              <p className="shell-player__sheet-title">{strings.label(s.label_key)}</p>
              <DestinationList section={s} currentKey={current?.key} onPick={() => setOpen(null)} />
            </div>
          ))}
        </div>
      ) : null}
      {library ? (
        <button
          type="button"
          className="shell-player__library"
          aria-expanded={open === "library"}
          aria-label={t("shell:player.library")}
          onClick={() => setOpen(open === "library" ? null : "library")}
        >
          <Icon name="library" size={20} />
        </button>
      ) : null}
      <div className="shell-player__track">
        <span className="shell-player__cover">
          <Icon name={page?.icon ?? here?.icon ?? "music"} size={22} />
        </span>
        <span className="shell-player__text">
          <strong>{page ? strings.label(page.label_key) : here ? strings.label(here.label_key) : "—"}</strong>
          <small>{here ? strings.label(here.label_key) : ""}</small>
        </span>
      </div>
      <div className="shell-player__controls">
        <div className="shell-player__buttons">
          <button
            type="button"
            aria-label={t("shell:player.shuffle")}
            title={t("shell:player.shuffle")}
            onClick={shuffle}
          >
            <Icon name="shuffle" size={18} />
          </button>
          <button
            type="button"
            aria-label={t("shell:player.previous")}
            title={t("shell:player.previous")}
            onClick={() => go(-1)}
          >
            <Icon name="skip-back" size={20} />
          </button>
          <NavLink to="/" end className="shell-player__play" aria-label={strings.label("nav:nav.home")}>
            <Icon name="play" size={20} />
          </NavLink>
          <button
            type="button"
            aria-label={t("shell:player.next")}
            title={t("shell:player.next")}
            onClick={() => go(1)}
          >
            <Icon name="skip-forward" size={20} />
          </button>
        </div>
        <span className="shell-player__progress" aria-hidden="true">
          <span style={{ inlineSize: `${Math.round(progress * 100)}%` }} />
        </span>
      </div>
      <span className="shell-player__extra">
        <Clock />
      </span>
    </nav>
  );
}

/** Masthead: the paper's name, its date and edition, then the sections as its columns. */
export function MastheadNav({ sections }: { sections: readonly NavSection[] }) {
  const strings = useShellStrings();
  const t = useT();
  const { current, isActive } = useCurrent(sections);
  const { open, setOpen, root } = useOpenSection();
  const section = sections.find((s) => s.key === open);
  const today = new Date();
  return (
    <nav ref={root} className="shell-masthead" aria-label={strings.mainNav}>
      <div className="shell-masthead__head" aria-hidden="true">
        <span className="shell-masthead__edition">{t("shell:masthead.edition")}</span>
        <span className="shell-masthead__title">{t("shell:masthead.title")}</span>
        <span className="shell-masthead__date">
          {today.toLocaleDateString(undefined, {
            weekday: "long",
            day: "numeric",
            month: "long",
            year: "numeric",
          })}
        </span>
      </div>
      {/* biome-ignore lint/a11y/noNoninteractiveElementInteractions: arrow keys move along the columns */}
      <ul className="shell-masthead__sections" onKeyDown={(event) => moveFocus(event)}>
        {sections.map((s) => (
          <li key={s.key}>
            <SectionItem
              section={s}
              active={isActive(s)}
              open={open === s.key}
              onToggle={() => setOpen(open === s.key ? null : s.key)}
              className="shell-masthead__section"
            />
          </li>
        ))}
      </ul>
      <SectionPanel section={section} currentKey={current?.key} className="shell-masthead__panel" />
    </nav>
  );
}
