import { useQuery } from "@tanstack/react-query";
import { Fragment, type KeyboardEvent, useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation, useNavigate } from "react-router";
import { api } from "../../api/client";
import { useAnnounce } from "../../design-system/a11y/Announce";
import { Icon } from "../../design-system/components/Icon";
import { kindKey, resolvePalette, useHistory } from "../../features/search/api";
import { useT } from "../../i18n/hooks/useT";
import { useNavigationView } from "../nav/NavigationProvider";
import { fromNavigation, rank } from "../palette/CommandRegistry";
import { useShellStrings } from "../strings";

/**
 * Search in the header (027): a field that answers while one types — the matching pages of the portal,
 * then the first results of each kind (titles, members, articles, tickets…) with a line of context, then
 * « all the results ». Nothing is listed before typing but the recent searches. Arrow keys move, Enter
 * opens, Escape closes; Ctrl/⌘ K and « / » focus it. On a phone the magnifier opens it over the header.
 */
interface Suggestion {
  kind: string;
  id: string;
  title: string;
  url_ref: string;
  snippet?: string;
  facets?: Record<string, string>;
  group?: string;
}

interface Option {
  id: string;
  group: string;
  icon: string;
  title: string;
  detail?: string | undefined;
  route: string;
}

const KIND_ICONS: Record<string, string> = {
  media: "film",
  wiki: "book",
  news: "newspaper",
  users: "user",
  services: "server",
  incidents: "alert",
  tickets: "ticket",
  feedback: "message",
  navigation: "compass",
  calendar: "calendar",
  community: "users",
  marketplace: "shop",
};

let focusHandler: ((query: string) => void) | null = null;

/** Focus the header's search (Ctrl/⌘ K, « / »); ``false`` when the header has none (another layout). */
export function focusHeaderSearch(query = ""): boolean {
  if (!focusHandler) return false;
  focusHandler(query);
  return true;
}

function useDebounced(value: string, delay = 180): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export function HeaderSearch({ phone = false }: { phone?: boolean }) {
  const t = useT();
  const strings = useShellStrings();
  const navigate = useNavigate();
  const location = useLocation();
  const { view } = useNavigationView();
  const ids = { input: useId(), list: useId() };
  const input = useRef<HTMLInputElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(false); // phone: the search covers the header
  const [active, setActive] = useState(-1);
  const text = useDebounced(query.trim());
  const results = useQuery({
    queryKey: ["search", "suggest", text],
    enabled: open && text.length > 0,
    staleTime: 30_000,
    retry: false,
    queryFn: async () =>
      ((
        (await api.GET("/api/v1/search/suggest", { params: { query: { q: text } } })).data as unknown as {
          items?: Suggestion[];
        }
      )?.items ?? []) as Suggestion[],
  });
  const resolution = useQuery({
    queryKey: ["search", "resolve", text],
    enabled: open && text.length > 0,
    staleTime: 30_000,
    retry: false,
    queryFn: () => resolvePalette(text, location.pathname),
  });
  const history = useHistory();
  const announce = useAnnounce();
  const pages = useMemo(
    () => fromNavigation(view.commands, strings.label, {}).filter((c) => c.route),
    [view.commands, strings.label],
  );

  useEffect(() => {
    focusHandler = (q: string) => {
      setQuery(q);
      setOpen(true);
      if (phone) setExpanded(true);
      window.setTimeout(() => input.current?.focus(), 0);
    };
    return () => {
      focusHandler = null;
    };
  }, [phone]);

  const options: Option[] = useMemo(() => {
    const out: Option[] = [];
    const q = query.trim();
    if (!q) {
      for (const entry of (Array.isArray(history.data) ? history.data : []).slice(0, 5)) {
        out.push({
          id: `history:${entry.id}`,
          group: t("shell:searchRecent"),
          icon: "clock",
          title: entry.query,
          route: `/search?q=${encodeURIComponent(entry.query)}`,
        });
      }
      return out;
    }
    const object = resolution.data?.object;
    if (object) {
      out.push({
        id: `object:${object.kind}:${object.id}`,
        group: t("shell:searchPages"),
        icon: KIND_ICONS[object.kind] ?? "search",
        title: t("search:palette.open", { title: object.title }),
        route: object.route,
      });
    }
    for (const page of rank(
      pages.filter((p) => !p.sensitive),
      q,
      4,
    )) {
      out.push({
        id: `page:${page.id}`,
        group: t("shell:searchPages"),
        icon: "compass",
        title: page.label,
        route: page.route as string,
      });
    }
    const seen = new Set(out.map((o) => o.route));
    for (const item of Array.isArray(results.data) ? results.data : []) {
      if (!item.url_ref.startsWith("/") || seen.has(item.url_ref)) continue;
      seen.add(item.url_ref);
      out.push({
        id: `result:${item.kind}:${item.id}`,
        group: t(item.group?.includes(":") ? item.group : kindKey(item.group ?? `search.kind.${item.kind}`)),
        icon: KIND_ICONS[item.kind] ?? "search",
        title: item.title,
        detail: detailOf(t, item),
        route: item.url_ref,
      });
    }
    out.push({
      id: "all",
      group: "",
      icon: "search",
      title: t("search:palette.searchFor", { query: q }),
      route: `/search?q=${encodeURIComponent(q)}`,
    });
    return out;
  }, [query, history.data, pages, results.data, resolution.data, t]);

  // while typing, the best match is ready for Enter; the count is announced
  const typed = query.trim().length > 0;
  useEffect(() => {
    if (!typed) return;
    setActive(options.length ? 0 : -1);
    announce(t("shell:searchCount", { count: Math.max(0, options.length - 1) }));
  }, [typed, options.length, announce, t]);

  const close = () => {
    setOpen(false);
    setExpanded(false);
    setActive(-1);
  };
  const choose = (option: Option) => {
    close();
    setQuery("");
    input.current?.blur();
    navigate(option.route);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActive((i) => (options.length ? (i + 1) % options.length : -1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => (options.length ? (i <= 0 ? options.length - 1 : i - 1) : -1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const chosen = options[active] ?? options.find((o) => o.id === "all");
      if (chosen) choose(chosen);
    } else if (event.key === "Escape") {
      if (query) setQuery("");
      else {
        close();
        input.current?.blur();
      }
    }
  };
  const showList = open && (options.length > 0 || (query.trim() && results.isFetching));
  let lastGroup = "";
  const field = (
    <div
      ref={box}
      className="header-search"
      data-phone={phone || undefined}
      data-open={showList || undefined}
    >
      <div className="header-search__field">
        {phone ? (
          <button
            type="button"
            className="header-search__back"
            aria-label={t("shell:searchClose")}
            onClick={() => {
              close();
              setQuery("");
            }}
          >
            <Icon name="chevron-left" size={20} />
          </button>
        ) : (
          <Icon name="search" size={18} />
        )}
        <input
          ref={input}
          id={ids.input}
          type="search"
          role="combobox"
          aria-expanded={Boolean(showList)}
          aria-controls={ids.list}
          aria-autocomplete="list"
          aria-activedescendant={active >= 0 ? `${ids.list}-${active}` : undefined}
          aria-label={strings.search}
          aria-keyshortcuts="Control+K Meta+K /"
          placeholder={strings.searchPlaceholder}
          autoComplete="off"
          spellCheck={false}
          value={query}
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
            setActive(-1);
          }}
          onKeyDown={onKeyDown}
          onBlur={(event) => {
            if (!box.current?.contains(event.relatedTarget as Node | null)) {
              setOpen(false);
              if (!query) setExpanded(false);
            }
          }}
        />
        {results.isFetching && query.trim() ? (
          <Icon name="spinner" size={16} className="header-search__spin" />
        ) : query ? (
          <button
            type="button"
            className="header-search__clear"
            aria-label={t("shell:searchClear")}
            onClick={() => {
              setQuery("");
              input.current?.focus();
            }}
          >
            <Icon name="close" size={16} />
          </button>
        ) : phone ? null : (
          <span className="header-search__kbd" aria-hidden="true">
            ⌘K
          </span>
        )}
      </div>
      {showList ? (
        <div id={ids.list} role="listbox" className="header-search__list" aria-label={strings.search}>
          {options.map((option, index) => {
            const heading =
              option.group && option.group !== lastGroup ? (
                <div className="header-search__group" aria-hidden="true">
                  {option.group}
                </div>
              ) : null;
            lastGroup = option.group || lastGroup;
            return (
              <Fragment key={option.id}>
                {heading}
                <div
                  id={`${ids.list}-${index}`}
                  role="option"
                  tabIndex={-1}
                  aria-selected={index === active}
                  className="header-search__option"
                  data-all={option.id === "all" || undefined}
                  onMouseDown={(e) => e.preventDefault()}
                  onMouseEnter={() => setActive(index)}
                  onClick={() => choose(option)}
                  onKeyDown={() => undefined}
                >
                  <span className="header-search__icon" aria-hidden="true">
                    <Icon name={option.icon} size={16} />
                  </span>
                  <span className="header-search__text">
                    <span className="header-search__title">
                      <Highlight text={option.title} query={option.id === "all" ? "" : query.trim()} />
                    </span>
                    {option.detail ? <span className="header-search__detail">{option.detail}</span> : null}
                  </span>
                  <Icon name="chevron-right" size={14} className="header-search__go" />
                </div>
              </Fragment>
            );
          })}
          {query.trim() && results.isSuccess && options.length <= 1 ? (
            <p className="header-search__none">{t("shell:searchNone")}</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
  if (!phone) return field;
  return (
    <>
      <button
        type="button"
        className="ds-button ds-button--ghost ds-button--icon"
        aria-label={strings.search}
        aria-keyshortcuts="Control+K Meta+K /"
        onClick={() => {
          setExpanded(true);
          setOpen(true);
          window.setTimeout(() => input.current?.focus(), 0);
        }}
      >
        <Icon name="search" />
      </button>
      {expanded ? createPortal(<div className="header-search__sheet">{field}</div>, document.body) : null}
    </>
  );
}

function detailOf(t: ReturnType<typeof useT>, item: Suggestion): string | undefined {
  const facets = item.facets ?? {};
  if (item.kind === "media") {
    const parts = [
      facets.type ? t(`media:kind.${facets.type}`) : null,
      facets.year ?? null,
      facets.availability === "available" ? t("media:detail.available") : null,
    ].filter(Boolean);
    if (parts.length) return parts.join(" · ");
  }
  return item.snippet?.trim() || undefined;
}

/** The typed text in bold inside a title (plain text — never markup). */
function Highlight({ text, query }: { text: string; query: string }) {
  if (!query) return <>{text}</>;
  const at = text.toLowerCase().indexOf(query.toLowerCase());
  if (at < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, at)}
      <mark>{text.slice(at, at + query.length)}</mark>
      {text.slice(at + query.length)}
    </>
  );
}
