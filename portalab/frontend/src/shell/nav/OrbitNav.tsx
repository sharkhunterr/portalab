import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { useShellStrings } from "../strings";
import type { NavEntry, NavSection } from "./NavigationProvider";
import { currentEntry, sectionEntries } from "./SectionNav";

/**
 * Orbit navigation (spec 027 R24): a theme may replace the menu by a floating bubble; activating it makes
 * the sections gravitate around it, and choosing a section unfolds its pages beside the orbit. Same
 * destinations as every other variant. Keyboard: the bubble is a button (``aria-expanded``), arrows move
 * between sections, Enter opens one, Escape closes and returns focus to the bubble. Reduced motion: items
 * appear in place without the orbit animation (``data-motion="none"`` in CSS).
 */
export function OrbitNav({ sections }: { sections: readonly NavSection[] }) {
  const strings = useShellStrings();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [chosen, setChosen] = useState<string | null>(null);
  const bubble = useRef<HTMLButtonElement>(null);
  const items = useRef<Array<HTMLElement | null>>([]);
  const current = currentEntry(sections, location.pathname);

  // biome-ignore lint/correctness/useExhaustiveDependencies: close on navigation
  useEffect(() => {
    setOpen(false);
    setChosen(null);
  }, [location.pathname]);

  useEffect(() => {
    if (open) items.current[0]?.focus();
  }, [open]);

  const close = () => {
    setOpen(false);
    setChosen(null);
    bubble.current?.focus();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (!["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"].includes(event.key)) return;
    const list = items.current.filter(Boolean) as HTMLElement[];
    const index = list.indexOf(document.activeElement as HTMLElement);
    if (index < 0) return;
    event.preventDefault();
    const step = event.key === "ArrowRight" || event.key === "ArrowDown" ? 1 : -1;
    list[(index + step + list.length) % list.length]?.focus();
  };

  const section = sections.find((s) => s.key === chosen);
  return (
    <div className="shell-orbit" data-open={open ? "true" : undefined}>
      {open ? (
        <button
          type="button"
          className="shell-orbit__scrim"
          aria-label={strings.closeMenu}
          onClick={close}
          tabIndex={-1}
        />
      ) : null}
      {open ? (
        <div
          className="shell-orbit__ring"
          role="dialog"
          aria-label={strings.mainNav}
          onKeyDown={onKeyDown}
          style={{ "--n": sections.length } as React.CSSProperties}
        >
          {sections.map((s, index) => {
            const active = sectionEntries(s).some((entry) => entry.key === current?.key);
            const style = { "--i": index } as React.CSSProperties;
            const label = strings.label(s.label_key);
            if (s.direct) {
              const entry = s.entries[0] as NavEntry;
              return (
                <NavLink
                  key={s.key}
                  ref={(node) => {
                    items.current[index] = node;
                  }}
                  to={entry.route ?? "/"}
                  end={entry.route === "/"}
                  className="shell-orbit__item"
                  data-active={active ? "true" : undefined}
                  style={style}
                  aria-label={label}
                  title={label}
                >
                  <Icon name={s.icon ?? entry.icon} />
                </NavLink>
              );
            }
            return (
              <button
                key={s.key}
                ref={(node) => {
                  items.current[index] = node;
                }}
                type="button"
                className="shell-orbit__item"
                data-active={active ? "true" : undefined}
                aria-expanded={chosen === s.key}
                style={style}
                aria-label={label}
                title={label}
                onClick={() => setChosen(chosen === s.key ? null : s.key)}
              >
                <Icon name={s.icon} />
              </button>
            );
          })}
          {section ? (
            <div className="shell-orbit__panel">
              <p className="shell-orbit__title">{strings.label(section.label_key)}</p>
              <ul className="shell-entries">
                {sectionEntries(section).map((entry) => (
                  <li key={entry.key}>
                    <NavLink
                      to={entry.route ?? "/"}
                      end
                      className="shell-entry"
                      aria-current={entry.key === current?.key ? "page" : undefined}
                    >
                      {strings.label(entry.label_key)}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
      <button
        ref={bubble}
        type="button"
        className="shell-orbit__bubble"
        aria-expanded={open}
        aria-label={open ? strings.closeMenu : strings.openNavigation}
        onClick={() => (open ? close() : setOpen(true))}
      >
        <Icon name={open ? "close" : "compass"} size={26} />
      </button>
    </div>
  );
}
