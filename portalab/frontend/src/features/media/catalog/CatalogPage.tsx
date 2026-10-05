import { type FormEvent, useId, useState } from "react";
import { useSearchParams } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { SelectField, TextField } from "../../../design-system/components/Field";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { type CatalogFilters, useCatalogPage } from "../api";
import { MediaGrid } from "../MediaGrid";
import "../media.css";
import { PageHeader } from "../../../design-system/components/PageHeader";

/** Catalog browse (spec 024 T014): text, kind, genre, year and availability filters; cursor pagination. */
const KINDS = ["movie", "series", "book", "audiobook", "game", "album"];

export function CatalogPage() {
  const t = useT();
  const headingId = useId();
  const [params] = useSearchParams();
  const initial: CatalogFilters = params.get("kind") ? { kind: params.get("kind") as string } : {}; // 027
  const [draft, setDraft] = useState<CatalogFilters>(initial);
  const [filters, setFilters] = useState<CatalogFilters>(initial);
  const page = useCatalogPage(filters);
  const items = (page.data?.pages ?? []).flatMap((p) => p.items);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    setFilters(draft);
  };
  return (
    <section aria-labelledby={headingId}>
      <PageHeader titleId={headingId} level={2} icon="film" title={t("media:catalog.title")} />
      <search>
        <form onSubmit={submit}>
          <fieldset className="media-filters">
            <legend className="visually-hidden">{t("media:catalog.title")}</legend>
            <TextField
              label={t("media:catalog.search")}
              value={draft.q ?? ""}
              onChange={(e) => setDraft({ ...draft, q: e.target.value })}
            />
            <SelectField
              label={t("media:catalog.kind")}
              value={draft.kind ?? ""}
              onChange={(e) => {
                const { kind: _, ...rest } = draft;
                setDraft(e.target.value ? { ...rest, kind: e.target.value } : rest);
              }}
            >
              <option value="">{t("media:catalog.all")}</option>
              {KINDS.map((k) => (
                <option key={k} value={k}>
                  {t(`media:kind.${k}`)}
                </option>
              ))}
            </SelectField>
            <TextField
              label={t("media:catalog.genre")}
              value={draft.genre ?? ""}
              onChange={(e) => setDraft({ ...draft, genre: e.target.value })}
            />
            <SelectField
              label={t("media:catalog.availability")}
              value={draft.availability ?? ""}
              onChange={(e) => {
                const { availability: _, ...rest } = draft;
                const value = e.target.value as CatalogFilters["availability"] | "";
                setDraft(value ? { ...rest, availability: value } : rest);
              }}
            >
              <option value="">{t("media:catalog.all")}</option>
              <option value="available">{t("media:catalog.available")}</option>
              <option value="unavailable">{t("media:catalog.unavailable")}</option>
            </SelectField>
            <Button type="submit">{t("media:catalog.apply")}</Button>
          </fieldset>
        </form>
      </search>
      {page.isPending ? <FunctionalState state="loading" /> : null}
      {page.isError ? <FunctionalState state="unavailable" onRetry={() => page.refetch()} /> : null}
      {page.isSuccess && items.length === 0 ? <p>{t("media:catalog.empty")}</p> : null}
      <MediaGrid items={items} label={t("media:catalog.title")} />
      {page.hasNextPage ? (
        <Button variant="secondary" onClick={() => page.fetchNextPage()}>
          {t("media:catalog.more")}
        </Button>
      ) : null}
    </section>
  );
}

export default CatalogPage;
