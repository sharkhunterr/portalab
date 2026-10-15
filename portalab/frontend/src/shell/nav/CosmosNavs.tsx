import { type CSSProperties, type KeyboardEvent, useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation } from "react-router";
import { levelProgress } from "../../design-system/components/Badges";
import { Icon } from "../../design-system/components/Icon";
import type { Progression } from "../../features/gamification/api";
import { useT } from "../../i18n/hooks/useT";
import { useShellStrings } from "../strings";
import type { NavSection } from "./NavigationProvider";
import {
  DestinationList,
  destinationsOf,
  moveFocus,
  opensList,
  useCurrent,
  useOpenSection,
} from "./PrincipleNavs";
import "../../design-system/themes/cosmos-navs.css";

/**
 * issue 130: the navigations of the cosmos (the third, the starship's deck plan, further down).
 *
 * - **Planisphere** (the Observatory): a round star chart that turns. Each section is a constellation on its
 *   rim — as many stars as it has pages — and turning the chart brings one into the window at the top, its
 *   pages listed beside it as stars to follow. Opened from the dome at the bottom of the screen; arrows (or
 *   the two buttons) turn it a section at a time, Enter follows, Escape closes and returns to the dome.
 * - **System** (the Space Station): a bar of planets on their orbit at the bottom — the home page the sun,
 *   each section a planet of its own size and colour; opening one shows its pages as moons going round it.
 *   Arrows move along the bar, Escape closes what is open.
 *
 * Same destinations as every other variant; reduced motion: no turning nor orbiting, everything in place.
 */

/** A stable small number from a key: the shape of a constellation, a planet's size and hue. */
function seedOf(key: string): number {
  let h = 2166136261;
  for (const char of key) h = Math.imul(h ^ (char.codePointAt(0) ?? 0), 16777619) >>> 0;
  return h;
}

/** A constellation of ``count`` stars for a section: points in a 40×40 box, joined in order. */
function constellation(key: string, count: number): Array<[number, number]> {
  let s = seedOf(key);
  const next = () => {
    s = Math.imul(s ^ (s >>> 15), 2246822507) >>> 0;
    s = Math.imul(s ^ (s >>> 13), 3266489909) >>> 0;
    return ((s ^ (s >>> 16)) >>> 0) / 4294967296;
  };
  const points: Array<[number, number]> = [];
  let x = 8 + next() * 8;
  let y = 12 + next() * 16;
  for (let i = 0; i < Math.max(2, Math.min(count, 7)); i++) {
    points.push([Math.round(x), Math.round(y)]);
    x = Math.min(34, x + 4 + next() * 7);
    y = Math.max(5, Math.min(35, y + (next() - 0.5) * 18));
  }
  return points;
}

function Constellation({ sectionKey, count }: { sectionKey: string; count: number }) {
  const points = constellation(sectionKey, count);
  return (
    <svg className="planisphere__stars" viewBox="0 0 40 40" aria-hidden="true" focusable="false">
      <polyline points={points.map(([x, y]) => `${x},${y}`).join(" ")} />
      {points.map(([x, y], i) => (
        <circle
          // biome-ignore lint/suspicious/noArrayIndexKey: the stars of one constellation, fixed
          key={i}
          cx={x}
          cy={y}
          r={i === 0 ? 2.2 : 1.6}
        />
      ))}
    </svg>
  );
}

export function PlanisphereNav({ sections }: { sections: readonly NavSection[] }) {
  const strings = useShellStrings();
  const location = useLocation();
  const { isActive } = useCurrent(sections);
  const [open, setOpen] = useState(false);
  const activeIndex = Math.max(
    0,
    sections.findIndex((s) => isActive(s)),
  );
  const [chosen, setChosen] = useState(activeIndex);
  const dome = useRef<HTMLButtonElement>(null);
  const items = useRef<Array<HTMLElement | null>>([]);
  const n = Math.max(sections.length, 1);

  // biome-ignore lint/correctness/useExhaustiveDependencies: close on navigation
  useEffect(() => setOpen(false), [location.pathname]);
  // biome-ignore lint/correctness/useExhaustiveDependencies: open on the section one is in
  useEffect(() => {
    if (open) {
      setChosen(activeIndex);
      items.current[activeIndex]?.focus();
    }
  }, [open]);

  const close = () => {
    setOpen(false);
    dome.current?.focus();
  };
  const turn = (step: number) => {
    const next = (chosen + step + n) % n;
    setChosen(next);
    items.current[next]?.focus();
  };
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
    } else if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      event.preventDefault();
      turn(1);
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      event.preventDefault();
      turn(-1);
    }
  };

  const section = sections[chosen];
  const current = sections[activeIndex];
  return (
    <div className="planisphere" data-open={open || undefined}>
      {open ? (
        <div
          className="planisphere__sky"
          role="dialog"
          aria-modal="true"
          aria-label={strings.mainNav}
          onKeyDown={onKeyDown}
        >
          <button
            type="button"
            className="planisphere__scrim"
            aria-label={strings.closeMenu}
            tabIndex={-1}
            onClick={close}
          />
          <div className="planisphere__chart">
            <div className="planisphere__window" aria-hidden="true" />
            <div
              className="planisphere__disc"
              style={{ "--turn": `${(-chosen * 360) / n}deg` } as CSSProperties}
            >
              <span className="planisphere__grid" aria-hidden="true" />
              {sections.map((s, index) => {
                const label = strings.label(s.label_key);
                const count = destinationsOf(s, undefined).length;
                return (
                  <button
                    key={s.key}
                    ref={(node) => {
                      items.current[index] = node;
                    }}
                    type="button"
                    className="planisphere__section"
                    style={{ "--a": `${(index * 360) / n}deg` } as CSSProperties}
                    data-chosen={index === chosen || undefined}
                    data-active={isActive(s) || undefined}
                    aria-pressed={index === chosen}
                    onClick={() => setChosen(index)}
                  >
                    <span className="planisphere__upright">
                      <Constellation sectionKey={s.key} count={count} />
                      <span className="planisphere__name">{label}</span>
                    </span>
                  </button>
                );
              })}
            </div>
            <button
              type="button"
              className="planisphere__turn"
              data-side="before"
              aria-label={strings.previousSection}
              onClick={() => turn(-1)}
            >
              <Icon name="chevron-left" />
            </button>
            <button
              type="button"
              className="planisphere__turn"
              data-side="after"
              aria-label={strings.nextSection}
              onClick={() => turn(1)}
            >
              <Icon name="chevron-right" />
            </button>
          </div>
          {section ? (
            <div className="planisphere__panel">
              <p className="planisphere__title">
                <Icon name={section.icon ?? "star"} size={18} />
                {strings.label(section.label_key)}
              </p>
              {destinationsOf(section, undefined).length > 1 ? (
                <DestinationList section={section} currentKey={undefined} className="planisphere__pages" />
              ) : (
                <NavLink to={destinationsOf(section, undefined)[0]?.route ?? "/"} className="planisphere__go">
                  <Icon name="telescope" size={16} />
                  {strings.label(section.label_key)}
                </NavLink>
              )}
            </div>
          ) : null}
        </div>
      ) : null}
      <button
        ref={dome}
        type="button"
        className="planisphere__dome"
        aria-expanded={open}
        aria-label={open ? strings.closeMenu : strings.openNavigation}
        onClick={() => (open ? close() : setOpen(true))}
      >
        <span className="planisphere__slit" aria-hidden="true" />
        <Icon name={open ? "close" : "telescope"} size={24} />
        {current && !open ? (
          <span className="planisphere__here">{strings.label(current.label_key)}</span>
        ) : null}
      </button>
    </div>
  );
}

/** How many cells the starship's energy gauge has. */
const CELLS = 10;

/**
 * issue 130: the third interface of the cosmos — **Deck plan** (the Starship). The ship seen from the side
 * along the bottom of the screen: its engines burning at the stern, a HUD (the energy gauge — the level's XP —
 * and the comms light, lit while messages wait), then one compartment per section, numbered like the decks,
 * up to the bow. A compartment with several pages opens its stations on a console screen above the hull.
 * Arrows move from compartment to compartment, Escape closes the console.
 */
export function DeckNav({
  sections,
  progression,
  unread,
}: {
  sections: readonly NavSection[];
  progression: Progression | null;
  unread: number | null;
}) {
  const t = useT();
  const strings = useShellStrings();
  const { current, isActive } = useCurrent(sections);
  const { open, setOpen, root } = useOpenSection();
  const openedIndex = sections.findIndex((s) => s.key === open);
  const opened = sections[openedIndex];
  const ratio = progression
    ? levelProgress(progression.xp, progression.level_floor, progression.next_level_at ?? null)
    : null;
  const lit = ratio === null ? 0 : Math.round(ratio * CELLS);
  const code = (index: number) => String(index + 1).padStart(2, "0");
  return (
    <nav className="deck" aria-label={strings.mainNav} ref={root as React.RefObject<HTMLElement>}>
      {opened ? (
        <div className="deck__console">
          <p className="deck__title">
            <span className="deck__code">{t("shell:deck.deck", { n: code(openedIndex) })}</span>
            {strings.label(opened.label_key)}
          </p>
          <DestinationList
            section={opened}
            currentKey={current?.key}
            className="deck__stations"
            onPick={() => setOpen(null)}
          />
        </div>
      ) : null}
      <div className="deck__ship">
        <span className="deck__engines" aria-hidden="true">
          <span className="deck__flame" />
          <span className="deck__flame" />
        </span>
        <div className="deck__hud">
          {progression && ratio !== null ? (
            <Link
              to="/progression"
              className="deck__gauge"
              aria-label={t("shell:deck.energyLabel", {
                level: progression.level,
                percent: Math.round(ratio * 100),
              })}
            >
              <span className="deck__gauge-name" aria-hidden="true">
                {t("shell:deck.energy")}
              </span>
              <span className="deck__cells" aria-hidden="true">
                {Array.from({ length: CELLS }, (_, i) => (
                  // biome-ignore lint/suspicious/noArrayIndexKey: the gauge's fixed cells
                  <span key={i} data-lit={i < lit || undefined} />
                ))}
              </span>
            </Link>
          ) : null}
          <Link
            to="/notifications"
            className="deck__comms"
            data-live={unread ? true : undefined}
            aria-label={unread ? t("shell:deck.commsWaiting", { count: unread }) : t("shell:deck.comms")}
          >
            <Icon name="radio" size={16} />
            {unread ? <span className="deck__comms-count">{unread > 99 ? "99+" : unread}</span> : null}
          </Link>
        </div>
        {/* biome-ignore lint/a11y/noNoninteractiveElementInteractions: arrows move along the hull */}
        <ol className="deck__rooms" onKeyDown={(event) => moveFocus(event)}>
          {sections.map((s, index) => {
            const label = strings.label(s.label_key);
            const first = destinationsOf(s, undefined)[0];
            const body = (
              <>
                <span className="deck__room-code" aria-hidden="true">
                  {code(index)}
                </span>
                <span className="deck__room-light" aria-hidden="true" />
                <Icon name={s.icon ?? first?.icon ?? "rocket"} size={18} />
                <span className="deck__room-name">{label}</span>
              </>
            );
            return (
              <li key={s.key}>
                {orbited(s) ? (
                  <button
                    type="button"
                    className="deck__room"
                    data-nav-item
                    data-active={isActive(s) || undefined}
                    aria-expanded={open === s.key}
                    onClick={() => setOpen(open === s.key ? null : s.key)}
                  >
                    {body}
                  </button>
                ) : (
                  <NavLink
                    to={first?.route ?? "/"}
                    end={first?.route === "/"}
                    className="deck__room"
                    data-nav-item
                    data-active={isActive(s) || undefined}
                    aria-current={isActive(s) ? "page" : undefined}
                  >
                    {body}
                  </NavLink>
                )}
              </li>
            );
          })}
        </ol>
        <span className="deck__bow" aria-hidden="true">
          <span className="deck__window" />
        </span>
      </div>
    </nav>
  );
}

/** A planet opens on its moons when it has more than one page (a member hub's pages, a list's entries). */
const orbited = (section: NavSection) => opensList(section) || destinationsOf(section, undefined).length > 1;

export function SystemNav({ sections }: { sections: readonly NavSection[] }) {
  const strings = useShellStrings();
  const { current, isActive } = useCurrent(sections);
  const { open, setOpen, root } = useOpenSection();
  const opened = sections.find((s) => s.key === open);
  return (
    <nav className="system" aria-label={strings.mainNav} ref={root as React.RefObject<HTMLElement>}>
      {opened ? (
        <div
          className="system__moons"
          style={{ "--n": destinationsOf(opened, undefined).length } as CSSProperties}
        >
          <p className="system__title">{strings.label(opened.label_key)}</p>
          <span
            className="system__body"
            aria-hidden="true"
            style={{ "--hue": seedOf(opened.key) % 360 } as CSSProperties}
          >
            <Icon name={opened.icon ?? "orbit"} size={26} />
          </span>
          <ul>
            {destinationsOf(opened, current?.key).map((destination, i) => (
              <li key={destination.key} style={{ "--i": i } as CSSProperties}>
                <NavLink
                  to={destination.route}
                  end
                  className="system__moon"
                  aria-current={destination.active ? "page" : undefined}
                  onClick={() => setOpen(null)}
                >
                  <span className="system__moon-dot" aria-hidden="true" />
                  {strings.label(destination.label_key)}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <span className="system__orbit" aria-hidden="true" />
      {/* biome-ignore lint/a11y/noNoninteractiveElementInteractions: arrows move along the bar */}
      <ol className="system__planets" onKeyDown={(event) => moveFocus(event)}>
        {sections.map((s, index) => {
          const label = strings.label(s.label_key);
          const first = destinationsOf(s, undefined)[0];
          const seed = seedOf(s.key);
          const style = {
            "--hue": seed % 360,
            "--size": `${2.1 + ((seed >>> 8) % 5) * 0.22}rem`,
            "--rise": `${((seed >>> 12) % 3) * 0.35}rem`,
          } as CSSProperties;
          const sun = index === 0;
          const body = (
            <>
              <span className="system__planet-body" data-ringed={(seed >>> 4) % 4 === 0 || undefined}>
                <Icon name={s.icon ?? first?.icon ?? "orbit"} size={18} />
              </span>
              <span className="system__planet-name">{label}</span>
            </>
          );
          return (
            <li key={s.key} style={style} data-sun={sun || undefined}>
              {orbited(s) ? (
                <button
                  type="button"
                  className="system__planet"
                  data-nav-item
                  data-active={isActive(s) || undefined}
                  aria-expanded={open === s.key}
                  onClick={() => setOpen(open === s.key ? null : s.key)}
                >
                  {body}
                </button>
              ) : (
                <NavLink
                  to={first?.route ?? "/"}
                  end={first?.route === "/"}
                  className="system__planet"
                  data-nav-item
                  data-active={isActive(s) || undefined}
                  aria-current={isActive(s) ? "page" : undefined}
                >
                  {body}
                </NavLink>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
