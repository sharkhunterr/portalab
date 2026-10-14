import { useEffect, useId, useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { type CatalogFacets, type CatalogFilters, useCatalogFacets, useCatalogPage } from "../api";
import { KIND_ICONS, MediaGrid } from "../MediaGrid";
import "../media.css";
import "./catalog.css";

/**
 * Catalog (spec 024 T014; issue 111): every title of the library, filtered as one browses — a search, the
 * kinds as chips, then the filters of the kind chosen (genre, years, availability, what I already watched,
 * read or played, and the kind's own: director, author, narrator, series, language, platform, publisher),
 * the active ones as chips to remove, how many titles match and the order. The filters live in the address,
 * so a filtered catalog can be shared and the back button returns to it. On a phone the filters fold away.
 */
const KINDS = ["movie", "series", "book", "audiobook", "game", "album"];
type Field = keyof CatalogFilters;
interface KindField {
  key: Field;
  facet: keyof CatalogFacets;
  /** many values (people): typed, with suggestions — else a list to choose from */
  typed?: boolean;
}
const KIND_FIELDS: Record<string, KindField[]> = {
  movie: [{ key: "director", facet: "directors", typed: true }],
  series: [{ key: "director", facet: "directors", typed: true }],
  book: [
    { key: "author", facet: "authors", typed: true },
    { key: "series", facet: "series", typed: true },
    { key: "language", facet: "languages" },
    { key: "publisher", facet: "publishers", typed: true },
  ],
  audiobook: [
    { key: "author", facet: "authors", typed: true },
    { key: "narrator", facet: "narrators", typed: true },
    { key: "series", facet: "series", typed: true },
    { key: "language", facet: "languages" },
  ],
  game: [
    { key: "platform", facet: "platforms" },
    { key: "publisher", facet: "publishers", typed: true },
  ],
};
const NUMBERS: Field[] = ["year", "year_from", "year_to"];
const ALL: Field[] = [
  "q",
  "kind",
  "genre",
  "year_from",
  "year_to",
  "availability",
  "seen",
  "author",
  "narrator",
  "director",
  "series",
  "language",
  "platform",
  "publisher",
  "sort",
  "year",
];

function read(params: URLSearchParams): CatalogFilters {
  const out: Record<string, string | number> = {};
  for (const key of ALL) {
    const value = params.get(key);
    if (!value) continue;
    out[key] = NUMBERS.includes(key) ? Number(value) : value;
  }
  return out as CatalogFilters;
}

/** A text typed in is applied once the member pauses (no button to press). */
function useSettled(value: string, apply: (value: string) => void) {
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);
  useEffect(() => {
    if (draft === value) return;
    const timer = window.setTimeout(() => apply(draft), 350);
    return () => window.clearTimeout(timer);
  }, [draft, value, apply]);
  return [draft, setDraft] as const;
}

function TypedField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  const listId = useId();
  const [draft, setDraft] = useSettled(value, onChange);
  return (
    <>
      <TextField
        label={label}
        value={draft}
        list={listId}
        autoComplete="off"
        onChange={(event) => setDraft(event.target.value)}
      />
      <datalist id={listId}>
        {options.slice(0, 200).map((option) => (
          <option key={option} value={option} />
        ))}
      </datalist>
    </>
  );
}

export function CatalogPage() {
  const t = useT();
  const format = useFormat();
  const headingId = useId();
  const panelId = useId();
  const [params, setParams] = useSearchParams();
  const filters = useMemo(() => read(params), [params]);
  const [open, setOpen] = useState(false);
  const page = useCatalogPage(filters);
  const facets = useCatalogFacets(filters.kind);
  const items = (page.data?.pages ?? []).flatMap((p) => p.items);
  const total = page.data?.pages[0]?.total ?? null;
  const languages = useMemo(() => {
    try {
      return new Intl.DisplayNames([document.documentElement.lang || "en"], { type: "language" });
    } catch {
      return null;
    }
  }, []);
  const language = (code: string) => {
    try {
      return languages?.of(code) ?? code;
    } catch {
      return code;
    }
  };

  const set = (changes: Partial<Record<Field, string | number | undefined>>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value === undefined || value === "" || (typeof value === "number" && Number.isNaN(value))) {
        next.delete(key);
      } else next.set(key, String(value));
    }
    setParams(next, { replace: true });
  };
  const chooseKind = (kind: string | undefined) => {
    // another kind: its own fields (and genres) start over
    const reset: Partial<Record<Field, undefined>> = { genre: undefined };
    for (const fields of Object.values(KIND_FIELDS)) for (const f of fields) reset[f.key] = undefined;
    set({ ...reset, kind });
  };
  const [q, setQ] = useSettled(filters.q ?? "", (value) => set({ q: value }));
  const fields = KIND_FIELDS[filters.kind ?? ""] ?? [];
  const label = (key: Field) => t(`media:catalog.field.${key}`);

  // the active filters, each one a chip to remove (the kind has its own chips)
  const active: Array<{ key: Field; text: string }> = [];
  if (filters.genre) active.push({ key: "genre", text: filters.genre });
  if (filters.year_from || filters.year_to) {
    active.push({
      key: "year_from",
      text: `${filters.year_from ?? "…"} – ${filters.year_to ?? "…"}`,
    });
  }
  if (filters.year) active.push({ key: "year", text: String(filters.year) });
  if (filters.availability)
    active.push({ key: "availability", text: t(`media:catalog.${filters.availability}`) });
  if (filters.seen) active.push({ key: "seen", text: t(`media:catalog.seenAs.${filters.seen}`) });
  for (const field of fields) {
    const value = filters[field.key];
    if (value) {
      active.push({
        key: field.key,
        text: `${label(field.key)} : ${field.key === "language" ? language(String(value)) : value}`,
      });
    }
  }
  const clearAll = () => {
    const keep = new URLSearchParams();
    if (filters.kind) keep.set("kind", filters.kind);
    if (filters.sort) keep.set("sort", filters.sort);
    setParams(keep, { replace: true });
  };
  const remove = (key: Field) =>
    set(key === "year_from" ? { year_from: undefined, year_to: undefined } : { [key]: undefined });
  const years = facets.data?.years;
  const yearOptions = useMemo(() => {
    const low = years?.min ?? null;
    const high = years?.max ?? null;
    if (low === null || high === null) return [];
    return Array.from({ length: high - low + 1 }, (_, i) => high - i);
  }, [years?.min, years?.max]);

  return (
    <section aria-labelledby={headingId} className="catalog">
      <PageHeader
        titleId={headingId}
        level={2}
        icon="film"
        title={t("media:catalog.title")}
        context={total !== null ? t("media:catalog.count", { count: total }) : undefined}
      />
      <search className="catalog__search">
        <div className="catalog__bar">
          <TextField
            label={t("media:catalog.search")}
            placeholder={t("media:catalog.searchHint")}
            type="search"
            value={q}
            onChange={(event) => setQ(event.target.value)}
          />
          <SelectField
            label={t("media:catalog.sort")}
            value={filters.sort ?? "title"}
            onChange={(event) =>
              set({ sort: event.target.value === "title" ? undefined : event.target.value })
            }
          >
            {(["title", "added", "year"] as const).map((sort) => (
              <option key={sort} value={sort}>
                {t(`media:catalog.sortBy.${sort}`)}
              </option>
            ))}
          </SelectField>
          <Button
            variant="secondary"
            className="catalog__toggle"
            aria-expanded={open}
            aria-controls={panelId}
            onClick={() => setOpen(!open)}
          >
            <Icon name="sliders" size={16} />
            {t("media:catalog.filters", { count: active.length })}
          </Button>
        </div>
        <fieldset className="catalog__kinds">
          <legend className="visually-hidden">{t("media:catalog.kind")}</legend>
          <button
            type="button"
            className="catalog__kind"
            aria-pressed={!filters.kind}
            onClick={() => chooseKind(undefined)}
          >
            <Icon name="list" size={16} />
            {t("media:catalog.kinds.all")}
          </button>
          {KINDS.map((kind) => (
            <button
              key={kind}
              type="button"
              className="catalog__kind"
              aria-pressed={filters.kind === kind}
              onClick={() => chooseKind(kind)}
            >
              <Icon name={KIND_ICONS[kind] ?? "film"} size={16} />
              {t(`media:catalog.kinds.${kind}`)}
            </button>
          ))}
        </fieldset>
        <div className="catalog__filters" id={panelId} data-open={open || undefined}>
          <SelectField
            label={t("media:catalog.genre")}
            value={filters.genre ?? ""}
            onChange={(event) => set({ genre: event.target.value })}
          >
            <option value="">{t("media:catalog.all")}</option>
            {(facets.data?.genres ?? []).map((genre) => (
              <option key={genre} value={genre}>
                {genre}
              </option>
            ))}
          </SelectField>
          <div className="catalog__years">
            <SelectField
              label={t("media:catalog.yearFrom")}
              value={filters.year_from ? String(filters.year_from) : ""}
              onChange={(event) =>
                set({ year_from: event.target.value ? Number(event.target.value) : undefined })
              }
            >
              <option value="">{t("media:catalog.any")}</option>
              {yearOptions.map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </SelectField>
            <SelectField
              label={t("media:catalog.yearTo")}
              value={filters.year_to ? String(filters.year_to) : ""}
              onChange={(event) =>
                set({ year_to: event.target.value ? Number(event.target.value) : undefined })
              }
            >
              <option value="">{t("media:catalog.any")}</option>
              {yearOptions.map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </SelectField>
          </div>
          <SelectField
            label={t("media:catalog.availability")}
            value={filters.availability ?? ""}
            onChange={(event) => set({ availability: event.target.value })}
          >
            <option value="">{t("media:catalog.all")}</option>
            <option value="available">{t("media:catalog.available")}</option>
            <option value="unavailable">{t("media:catalog.unavailable")}</option>
          </SelectField>
          <SelectField
            label={t("media:catalog.seen")}
            value={filters.seen ?? ""}
            onChange={(event) => set({ seen: event.target.value })}
          >
            <option value="">{t("media:catalog.all")}</option>
            {(["unseen", "started", "finished"] as const).map((seen) => (
              <option key={seen} value={seen}>
                {t(`media:catalog.seenAs.${seen}`)}
              </option>
            ))}
          </SelectField>
          {fields.map((field) => {
            const options = (facets.data?.[field.facet] as string[] | undefined) ?? [];
            const value = String(filters[field.key] ?? "");
            return field.typed ? (
              <TypedField
                key={field.key}
                label={label(field.key)}
                value={value}
                options={options}
                onChange={(next) => set({ [field.key]: next })}
              />
            ) : (
              <SelectField
                key={field.key}
                label={label(field.key)}
                value={value}
                onChange={(event) => set({ [field.key]: event.target.value })}
              >
                <option value="">{t("media:catalog.all")}</option>
                {options.map((option) => (
                  <option key={option} value={option}>
                    {field.key === "language" ? language(option) : option}
                  </option>
                ))}
              </SelectField>
            );
          })}
        </div>
        {active.length ? (
          <ul className="catalog__active" aria-label={t("media:catalog.active")}>
            {active.map((chip) => (
              <li key={chip.key}>
                <button
                  type="button"
                  className="catalog__chip"
                  aria-label={t("media:catalog.remove", { name: chip.text })}
                  onClick={() => remove(chip.key)}
                >
                  {chip.text}
                  <Icon name="close" size={14} />
                </button>
              </li>
            ))}
            <li>
              <button type="button" className="ds-link catalog__clear" onClick={clearAll}>
                {t("media:catalog.clear")}
              </button>
            </li>
          </ul>
        ) : null}
      </search>
      {page.isPending ? <FunctionalState state="loading" /> : null}
      {page.isError ? <FunctionalState state="unavailable" onRetry={() => page.refetch()} /> : null}
      {page.isSuccess && items.length === 0 ? (
        <p className="catalog__empty">{t("media:catalog.empty")}</p>
      ) : null}
      <MediaGrid items={items} label={t("media:catalog.title")} />
      {page.hasNextPage ? (
        <div className="catalog__more">
          <Button variant="secondary" onClick={() => page.fetchNextPage()} disabled={page.isFetchingNextPage}>
            {t("media:catalog.more")}
          </Button>
          {total !== null ? (
            <span className="admin-muted">
              {t("media:catalog.shown", { shown: format.number(items.length), count: total })}
            </span>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

export default CatalogPage;
