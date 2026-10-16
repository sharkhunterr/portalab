import { type CSSProperties, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { useTheme } from "../../design-system/themes/ThemeProvider";
import type { ExternalElement } from "../../design-system/visuals/registry";
import { runSandbox, type Sandbox } from "../../design-system/visuals/sandbox";
import { useLocaleContext } from "../../i18n/provider/I18nProvider";
import { useShellStrings } from "../strings";
import type { NavSection } from "./NavigationProvider";
import { destinationsOf, useCurrent } from "./PrincipleNavs";
import "../../design-system/visuals/external.css";

/**
 * issue 1: a navigation an imported pack brings — drawn by its own script in a sandbox (an iframe of an opaque
 * origin: no account, no network, no page of Portalab's). It is handed what a navigation shows and nothing
 * more: the sections and pages this member may open (their keys, names and icons — never their addresses), the
 * current page, the interface's colours and fonts, a few words and counts. It may only ask to open one of
 * those keys: the interface checks it and opens the page itself.
 *
 * Its place is said by its pack (a bar along an edge, a floating button, its size; whether it may cover the
 * screen while open), so the page keeps its room before the script runs. The landmark, its name and the skip
 * link stay Portalab's. When the script does not answer in time or fails, ``onFail``: a built-in navigation
 * takes over. Never on a protected surface (the administration keeps its own navigation).
 */

const READY_MS = 4000;
const COLOURS = [
  "accent",
  "accent-alt",
  "accent-contrast",
  "surface",
  "surface-raised",
  "text",
  "text-muted",
  "border",
  "focus",
] as const;

export interface PackNavLayout {
  position: "top" | "bottom" | "left" | "right" | "floating";
  size: number;
  expands: boolean;
}

export function packNavLayout(element: ExternalElement): PackNavLayout {
  const nav: Partial<PackNavLayout> = element.nav ?? {};
  return {
    position: nav.position ?? "bottom",
    size: Math.min(320, Math.max(40, Number(nav.size) || 72)),
    expands: Boolean(nav.expands),
  };
}

interface Model {
  routes: Map<string, string>;
  sections: Array<{
    key: string;
    label: string;
    icon: string | null;
    active: boolean;
    entries: Array<{ key: string; label: string; icon: string | null; active: boolean }>;
  }>;
}

export function PackNav({
  element,
  sections,
  unread,
  level,
  coins,
  onFail,
}: {
  element: ExternalElement;
  sections: readonly NavSection[];
  unread: number | null;
  level: number | null;
  coins: number | null;
  onFail: () => void;
}) {
  const strings = useShellStrings();
  const navigate = useNavigate();
  const { current, isActive } = useCurrent(sections);
  const { effective } = useTheme();
  const { language } = useLocaleContext();
  const layout = packNavLayout(element);
  const frame = useRef<HTMLIFrameElement>(null);
  const icons = useRef<HTMLSpanElement>(null);
  const sandbox = useRef<Sandbox | null>(null);
  const [expanded, setExpanded] = useState(false);
  const failed = useRef(onFail);
  failed.current = onFail;

  // what the navigation may know: keys, names, icons, the current page — the addresses stay here
  const model = useMemo<Model>(() => {
    const routes = new Map<string, string>();
    const out: Model["sections"] = sections.map((section) => {
      const entries = destinationsOf(section, current?.key).map((destination) => {
        routes.set(destination.key, destination.route);
        return {
          key: destination.key,
          label: strings.label(destination.label_key),
          icon: destination.icon ?? null,
          active: destination.active,
        };
      });
      const first = entries[0];
      if (first) routes.set(section.key, routes.get(first.key) ?? "/");
      return {
        key: section.key,
        label: strings.label(section.label_key),
        icon: section.icon ?? first?.icon ?? null,
        active: isActive(section),
        entries,
      };
    });
    return { routes, sections: out };
  }, [sections, current?.key, strings, isActive]);

  const context = (): Record<string, unknown> => {
    const style = getComputedStyle(document.documentElement);
    const markup = new Map<string, string>();
    for (const node of icons.current?.querySelectorAll<HTMLElement>("[data-icon-for]") ?? []) {
      markup.set(node.dataset.iconFor ?? "", node.innerHTML);
    }
    return {
      type: "navigation",
      look: element.look,
      language,
      device: window.matchMedia("(max-width: 47.99rem)").matches ? "phone" : "desktop",
      reducedMotion: effective.reducedMotion,
      layout,
      sections: model.sections.map((s) => ({
        ...s,
        icon: s.icon ? (markup.get(s.icon) ?? null) : null,
        entries: s.entries.map((e) => ({ ...e, icon: e.icon ? (markup.get(e.icon) ?? null) : null })),
      })),
      current: current?.key ?? null,
      colors: Object.fromEntries(
        COLOURS.map((name) => [name, style.getPropertyValue(`--color-${name}`).trim()]),
      ),
      fonts: {
        body: effective.theme.typography?.fontFamily ?? "system-ui, sans-serif",
        heading: effective.theme.typography?.headingFamily ?? "system-ui, sans-serif",
      },
      strings: {
        mainNav: strings.mainNav,
        home: strings.home,
        close: strings.closeMenu,
        open: strings.openNavigation,
      },
      counts: { unread: unread ?? 0 },
      me: { level, coins },
    };
  };
  const latest = useRef(context);
  latest.current = context;
  const routes = useRef(model.routes);
  routes.current = model.routes;

  // biome-ignore lint/correctness/useExhaustiveDependencies: one sandbox per navigation element
  useEffect(() => {
    const target = frame.current;
    if (!target) return;
    let ready = false;
    const timer = window.setTimeout(() => {
      if (!ready) failed.current();
    }, READY_MS);
    sandbox.current = runSandbox(target, element, latest.current(), {
      onReady: () => {
        ready = true;
      },
      onError: (message) => {
        console.warn("pack navigation:", element.product, message);
        failed.current();
      },
      onNavigate: (key) => {
        const route = routes.current.get(key); // only a page it was given
        if (route) {
          setExpanded(false);
          navigate(route);
        }
      },
      onExpand: (open) => setExpanded(layout.expands && open),
    });
    return () => {
      window.clearTimeout(timer);
      sandbox.current?.stop();
      sandbox.current = null;
    };
  }, [element]);

  // the page changed, or the counts: the navigation is told
  // biome-ignore lint/correctness/useExhaustiveDependencies: what the navigation knows follows the page
  useEffect(() => {
    sandbox.current?.update(latest.current());
  }, [model, unread, level, coins, effective.theme.key, effective.reducedMotion]);

  const iconNames = useMemo(() => {
    const names = new Set<string>();
    for (const s of model.sections) {
      if (s.icon) names.add(s.icon);
      for (const e of s.entries) if (e.icon) names.add(e.icon);
    }
    return [...names];
  }, [model]);

  return (
    <nav
      className="pack-nav"
      aria-label={strings.mainNav}
      data-position={layout.position}
      data-expanded={expanded || undefined}
      style={{ "--pack-nav-size": `${layout.size}px` } as CSSProperties}
    >
      <iframe
        ref={frame}
        className="pack-nav__frame"
        data-sandboxed=""
        data-external={element.product}
        sandbox="allow-scripts"
        title={strings.mainNav}
      />
      <span ref={icons} hidden aria-hidden="true">
        {iconNames.map((name) => (
          <span key={name} data-icon-for={name}>
            <Icon name={name} size={20} />
          </span>
        ))}
      </span>
    </nav>
  );
}
