import { useId } from "react";
import { NavLink, useLocation, useNavigate } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { Menu, Popover } from "../../design-system/components/Overlays";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useShellPreference } from "../preferences";
import { useShellStrings } from "../strings";
import { type NavEntry, type NavSection, type NavTopic, useNavigationView } from "./NavigationProvider";

/**
 * Section navigation (spec 027 US2, FR-008…FR-017): named sections with icons instead of a flat list.
 * A single-entry section is a direct link; others expand (``aria-expanded``) to their pages, Administration
 * shows its topics as sub-headings. The current page and its section are marked and the section opens on
 * arrival; the sections a user keeps open follow them across devices (``shell.navigation.expanded``).
 * Variants: ``list`` (sidebar, drawer), ``rail`` (icons + flyouts), ``bar`` (top bar with menus).
 */
export function isCurrent(route: string | null | undefined, pathname: string): boolean {
  if (!route) return false;
  if (route === "/") return pathname === "/";
  return pathname === route || pathname.startsWith(`${route}/`);
}

export function sectionEntries(section: NavSection): NavEntry[] {
  return [...section.entries, ...section.topics.flatMap((topic) => topic.entries)];
}

/** The entry whose route best matches the location (longest prefix), so /admin/x does not light /admin. */
export function currentEntry(sections: readonly NavSection[], pathname: string): NavEntry | undefined {
  return sections
    .flatMap(sectionEntries)
    .filter((entry) => isCurrent(entry.route, pathname))
    .sort((a, b) => (b.route?.length ?? 0) - (a.route?.length ?? 0))[0];
}

/** A place grouping related pages, shown as tabs above the content (027). */
export interface Hub {
  key: string;
  label_key: string;
  icon?: string | null | undefined;
  entries: NavEntry[];
  audience: string;
}

/**
 * Member sections are hubs too (027): one link in the navigation (to their first page) and their pages as
 * tabs — the same spirit as the Administration hubs. A single-page section stays a direct link.
 */
export function isHubSection(section: NavSection): boolean {
  return section.audience !== "administration" && !section.direct && sectionEntries(section).length > 1;
}

/** The hub holding the current page: an Administration hub, a member section or « My account » (027). */
export function currentHub(sections: readonly NavSection[], pathname: string): Hub | undefined {
  const entry = currentEntry(sections, pathname);
  if (!entry) return undefined;
  for (const section of sections) {
    if (section.audience === "administration") {
      const topic = section.topics.find((t: NavTopic) => t.entries.some((e) => e.key === entry.key));
      if (topic) return { ...topic, icon: topic.icon, audience: section.audience };
    } else if (sectionEntries(section).some((e) => e.key === entry.key)) {
      return {
        key: section.key,
        label_key: section.label_key,
        icon: section.icon,
        entries: sectionEntries(section),
        audience: section.audience,
      };
    }
  }
  return undefined;
}

export interface SectionNavProps {
  sections: readonly NavSection[];
  variant?: "list" | "rail" | "bar";
  onNavigate?: (() => void) | undefined;
}

/** The navigation of the current view, with its loading and degraded states (004 FR-027). */
export function NavContent({ variant = "list", onNavigate }: Omit<SectionNavProps, "sections">) {
  const strings = useShellStrings();
  const { view, loading, failed } = useNavigationView();
  if (loading) return <FunctionalState state="loading" label={strings.mainNav} />;
  return (
    <>
      {failed || view.degraded ? <FunctionalState state="partial" label={strings.navDegraded} /> : null}
      <SectionNav sections={view.sections} variant={variant} onNavigate={onNavigate} />
    </>
  );
}

export function SectionNav({ sections, variant = "list", onNavigate }: SectionNavProps) {
  const location = useLocation();
  const [expanded, setExpanded] = useShellPreference<string[]>("shell.navigation.expanded", []);
  const current = currentEntry(sections, location.pathname);
  const toggle = (key: string, open: boolean) =>
    setExpanded(open ? [...new Set([...expanded, key])] : expanded.filter((k) => k !== key));
  return (
    <ul className={`shell-sections shell-sections--${variant}`}>
      {sections.map((section) => {
        const active = sectionEntries(section).some((entry) => entry.key === current?.key);
        const props = { section, active, currentKey: current?.key, onNavigate };
        if (section.direct || isHubSection(section)) {
          return (
            <li key={section.key}>
              <DirectLink {...props} compact={variant === "rail"} />
            </li>
          );
        }
        if (variant === "rail")
          return (
            <li key={section.key}>
              <RailSection {...props} />
            </li>
          );
        if (variant === "bar")
          return (
            <li key={section.key}>
              <BarSection {...props} />
            </li>
          );
        const open = active || expanded.includes(section.key);
        return (
          <li key={section.key}>
            <ListSection {...props} open={open} onToggle={(next) => toggle(section.key, next)} />
          </li>
        );
      })}
    </ul>
  );
}

interface ItemProps {
  section: NavSection;
  active: boolean;
  currentKey: string | undefined;
  onNavigate: (() => void) | undefined;
}

/** A direct link: a single-page section, or a member hub opening on its first page (its pages are tabs). */
function DirectLink({ section, active, onNavigate, compact = false }: ItemProps & { compact?: boolean }) {
  const strings = useShellStrings();
  const entry = sectionEntries(section)[0] as NavEntry;
  const label = strings.label(section.label_key);
  return (
    <NavLink
      to={entry.route ?? "/"}
      end={entry.route === "/"}
      className="shell-section__head"
      data-active={active ? "true" : undefined}
      aria-current={active ? (section.direct ? "page" : "true") : undefined}
      aria-label={compact ? label : undefined}
      title={compact ? label : undefined}
      onClick={onNavigate}
    >
      <Icon name={section.icon ?? entry.icon} />
      <span className="shell-section__label">{label}</span>
    </NavLink>
  );
}

function EntryLinks({ section, currentKey, onNavigate }: Omit<ItemProps, "active">) {
  const strings = useShellStrings();
  const link = (entry: NavEntry) => (
    <li key={entry.key}>
      <NavLink
        to={entry.route ?? "/"}
        end
        className="shell-entry"
        aria-current={entry.key === currentKey ? "page" : undefined}
        onClick={onNavigate}
      >
        {strings.label(entry.label_key)}
      </NavLink>
    </li>
  );
  if (section.audience === "administration") {
    // hubs: one link each (icon + label), current when the page belongs to it
    return (
      <ul className="shell-entries shell-hubs">
        {section.topics.map((topic) => {
          const current = topic.entries.some((entry) => entry.key === currentKey);
          return (
            <li key={topic.key}>
              <NavLink
                to={topic.route ?? topic.entries[0]?.route ?? "/admin"}
                end
                className="shell-entry shell-hub"
                aria-current={current ? "page" : undefined}
                data-active={current ? "true" : undefined}
                onClick={onNavigate}
              >
                <Icon name={topic.icon ?? "settings"} size={18} />
                {strings.label(topic.label_key)}
              </NavLink>
            </li>
          );
        })}
        {section.entries.map(link)}
      </ul>
    );
  }
  return (
    <>
      {section.entries.length ? <ul className="shell-entries">{section.entries.map(link)}</ul> : null}
      {section.topics.map((topic) => (
        <div key={topic.key} className="shell-topic">
          <p className="shell-topic__title">{strings.label(topic.label_key)}</p>
          <ul className="shell-entries">{topic.entries.map(link)}</ul>
        </div>
      ))}
    </>
  );
}

function ListSection({
  open,
  onToggle,
  ...props
}: ItemProps & { open: boolean; onToggle: (open: boolean) => void }) {
  const strings = useShellStrings();
  const panel = useId();
  return (
    <div className="shell-section" data-open={open ? "true" : undefined}>
      <button
        type="button"
        className="shell-section__head"
        data-active={props.active ? "true" : undefined}
        aria-expanded={open}
        aria-controls={panel}
        onClick={() => onToggle(!open)}
      >
        <Icon name={props.section.icon} />
        <span className="shell-section__label">{strings.label(props.section.label_key)}</span>
        <Icon name="chevron-down" size={16} className="shell-section__chevron" />
      </button>
      <div id={panel} className="shell-section__panel" hidden={!open}>
        <EntryLinks {...props} />
      </div>
    </div>
  );
}

/** Rail: icon buttons; a section opens a flyout panel with its pages (keyboard: Radix popover). */
function RailSection(props: ItemProps) {
  const strings = useShellStrings();
  const label = strings.label(props.section.label_key);
  return (
    <Popover
      label={label}
      trigger={
        <button
          type="button"
          className="shell-section__head"
          data-active={props.active ? "true" : undefined}
          aria-label={label}
          title={label}
        >
          <Icon name={props.section.icon} />
          <span className="shell-section__label">{label}</span>
        </button>
      }
    >
      <p className="shell-flyout__title">{label}</p>
      <EntryLinks {...props} />
    </Popover>
  );
}

/** Top bar: each section is a dropdown menu of its pages. */
function BarSection({ section, active, onNavigate }: ItemProps) {
  const strings = useShellStrings();
  const navigate = useNavigate();
  const items = (
    section.audience === "administration"
      ? section.topics.map((topic) => ({
          key: topic.key,
          label_key: topic.label_key,
          icon: topic.icon,
          route: topic.route ?? topic.entries[0]?.route ?? "/admin",
        }))
      : sectionEntries(section)
  ).map((entry) => ({
    key: entry.key,
    label: strings.label(entry.label_key),
    icon: entry.icon ?? undefined,
    onSelect: () => {
      navigate(entry.route ?? "/");
      onNavigate?.();
    },
  }));
  return (
    <Menu
      label={strings.label(section.label_key)}
      items={items}
      trigger={
        <button type="button" className="shell-section__head" data-active={active ? "true" : undefined}>
          <Icon name={section.icon} />
          <span className="shell-section__label">{strings.label(section.label_key)}</span>
          <Icon name="chevron-down" size={16} />
        </button>
      }
    />
  );
}
