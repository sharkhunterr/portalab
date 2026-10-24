import { useId, useMemo, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { PageHeader } from "../../design-system/components/PageHeader";
import { useT } from "../../i18n/hooks/useT";
import "./settings.css";

/**
 * « My settings » (issue 14): one place for everything a member sets — profile, appearance, language and
 * region, notifications, linked accounts, privacy, play — a list of pages by intent beside the page shown,
 * and a search through every setting. On a phone, the list is the page and each setting a page of its own,
 * with a way back. The pages keep their addresses (``/account``, ``/settings/appearance``, ``/privacy``…).
 */
export const SETTINGS_PAGES = [
  {
    key: "profile",
    to: "/account",
    icon: "user",
    items: ["name", "photo", "about", "presence", "password", "data", "delete"],
  },
  {
    key: "appearance",
    to: "/settings/appearance",
    icon: "palette",
    items: ["interface", "mode", "density", "text", "contrast", "motion", "sound", "toasts"],
  },
  {
    key: "language",
    to: "/settings/language",
    icon: "globe",
    items: ["language", "formats", "timezone", "clock", "week"],
  },
  { key: "notifications", to: "/settings/notifications", icon: "bell", items: ["channels", "email"] },
  { key: "accounts", to: "/settings/media-accounts", icon: "link", items: ["media"] },
  { key: "privacy", to: "/privacy", icon: "lock", items: ["visibility", "retention", "export"] },
  { key: "play", to: "/settings/play", icon: "gamepad", items: ["play", "cards", "presence"] },
] as const;

type Page = (typeof SETTINGS_PAGES)[number];

function matches(text: string, needle: string): boolean {
  const fold = (value: string) => value.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  return fold(text).includes(fold(needle));
}

/** What the search finds: a page by its name, or one of its settings by name and words. */
function useResults(needle: string) {
  const t = useT();
  return useMemo(() => {
    if (!needle.trim()) return [];
    const out: Array<{ page: Page; item: string | null; title: string; hint: string }> = [];
    for (const page of SETTINGS_PAGES) {
      const title = t(`account:settings.page.${page.key}`);
      if (matches(title, needle))
        out.push({ page, item: null, title, hint: t(`account:settings.hint.${page.key}`) });
      for (const item of page.items) {
        const name = t(`account:settings.item.${page.key}.${item}`);
        const words = t(`account:settings.words.${page.key}.${item}`);
        if (matches(`${name} ${words}`, needle)) out.push({ page, item, title: name, hint: title });
      }
    }
    return out;
  }, [needle, t]);
}

function SettingsSearch({ query, setQuery }: { query: string; setQuery: (value: string) => void }) {
  const t = useT();
  const id = useId();
  return (
    <search className="settings-search">
      <label htmlFor={id} className="visually-hidden">
        {t("account:settings.search")}
      </label>
      <Icon name="search" size={16} />
      <input
        id={id}
        type="search"
        value={query}
        placeholder={t("account:settings.search")}
        onChange={(event) => setQuery(event.target.value)}
      />
    </search>
  );
}

function PageList({ onPick }: { onPick?: () => void }) {
  const t = useT();
  const pages = SETTINGS_PAGES;
  return (
    <ul className="settings-hub__pages">
      {pages.map((page) => (
        <li key={page.key}>
          <NavLink to={page.to} onClick={onPick}>
            <Icon name={page.icon} size={18} />
            <span className="settings-hub__page">
              <strong>{t(`account:settings.page.${page.key}`)}</strong>
              <span>{t(`account:settings.hint.${page.key}`)}</span>
            </span>
            <Icon name="chevron-right" size={16} />
          </NavLink>
        </li>
      ))}
    </ul>
  );
}

function Results({ needle, onPick }: { needle: string; onPick: () => void }) {
  const t = useT();
  const results = useResults(needle);
  if (!results.length) return <p className="settings-hub__none">{t("account:settings.none")}</p>;
  return (
    <ul
      className="settings-hub__results"
      aria-label={t("account:settings.results", { count: results.length })}
    >
      {results.map((result) => (
        <li key={`${result.page.key}:${result.item ?? ""}`}>
          <Link to={result.page.to} onClick={onPick}>
            <Icon name={result.page.icon} size={16} />
            <span>
              <strong>{result.title}</strong>
              <span>{result.hint}</span>
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** The hub around every settings page: the list of pages and the search beside it (above it on a phone). */
export function SettingsLayout() {
  const t = useT();
  const location = useLocation();
  const [query, setQuery] = useState("");
  const home = location.pathname === "/settings";
  return (
    <div className="settings-hub" data-home={home || undefined}>
      <aside className="settings-hub__side" aria-label={t("account:settings.title")}>
        <Link to="/settings" className="settings-hub__title">
          <Icon name="settings" size={18} />
          {t("account:settings.title")}
        </Link>
        <SettingsSearch query={query} setQuery={setQuery} />
        {query.trim() ? <Results needle={query} onPick={() => setQuery("")} /> : <PageList />}
      </aside>
      <div className="settings-hub__main">
        {home ? null : (
          <Link to="/settings" className="settings-hub__back">
            <Icon name="back" size={16} />
            {t("account:settings.title")}
          </Link>
        )}
        <Outlet />
      </div>
    </div>
  );
}

/** ``/settings``: the pages by intent, each with what it holds (on a phone, the list is all there is). */
export function SettingsHome() {
  const t = useT();
  const headingId = useId();
  const pages = SETTINGS_PAGES;
  return (
    <section aria-labelledby={headingId} className="settings-home">
      <PageHeader
        titleId={headingId}
        icon="settings"
        title={t("account:settings.title")}
        context={t("account:settings.lead")}
      />
      <ul className="settings-home__grid">
        {pages.map((page) => (
          <li key={page.key}>
            <Link to={page.to} className="settings-home__card">
              <span className="settings-home__icon" aria-hidden="true">
                <Icon name={page.icon} size={22} />
              </span>
              <strong>{t(`account:settings.page.${page.key}`)}</strong>
              <span>{t(`account:settings.hint.${page.key}`)}</span>
              <span className="settings-home__items">
                {page.items
                  .slice(0, 4)
                  .map((item) => t(`account:settings.item.${page.key}.${item}`))
                  .join(" · ")}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default SettingsLayout;
