import { useId } from "react";
import { Button } from "../../../design-system/components/Button";
import { useT } from "../../../i18n/hooks/useT";
import { type GroupOut, kindKey, type SearchParams } from "../api";

/**
 * Filters (spec 008 T017; FR-010/011): restrict to a result type and to facet values declared by the
 * sources (counts cover permitted items only). Changing a filter updates the URL, so results update in
 * place without losing the query, and the view stays shareable and back-button friendly.
 */
export function FilterBar({
  groups,
  params,
  onChange,
}: {
  groups: GroupOut[];
  params: SearchParams;
  onChange: (next: SearchParams) => void;
}) {
  const t = useT();
  const legendId = useId();
  const kinds = groups.map((group) => ({ kind: group.kind, label: t(kindKey(group.label_key)) }));
  const facets = new Map<string, { label: string; values: Map<string, number> }>();
  for (const group of groups) {
    for (const facet of group.facets) {
      const entry = facets.get(facet.key) ?? { label: t(kindKey(facet.label_key)), values: new Map() };
      for (const [value, count] of Object.entries(facet.counts)) {
        entry.values.set(value, (entry.values.get(value) ?? 0) + count);
      }
      facets.set(facet.key, entry);
    }
  }
  const toggleKind = (kind: string) =>
    onChange({
      ...params,
      kinds: params.kinds.includes(kind) ? params.kinds.filter((k) => k !== kind) : [...params.kinds, kind],
    });
  const toggleValue = (key: string, value: string) => {
    const current = params.filters[key] ?? [];
    const next = current.includes(value) ? current.filter((v) => v !== value) : [...current, value];
    const filters = { ...params.filters, [key]: next };
    if (!next.length) delete filters[key];
    onChange({ ...params, filters });
  };
  const active = params.kinds.length > 0 || Object.keys(params.filters).length > 0;
  return (
    <fieldset className="search-filters" aria-labelledby={legendId}>
      <legend id={legendId}>{t("search:filters")}</legend>
      <fieldset className="ds-stack ds-stack--row search-filters__group">
        <legend className="visually-hidden">{t("search:allTypes")}</legend>
        {kinds.map(({ kind, label }) => (
          <Button
            key={kind}
            variant={params.kinds.includes(kind) ? "primary" : "secondary"}
            aria-pressed={params.kinds.includes(kind)}
            onClick={() => toggleKind(kind)}
          >
            {label}
          </Button>
        ))}
      </fieldset>
      {[...facets.entries()].map(([key, facet]) =>
        facet.values.size ? (
          <fieldset key={key} className="ds-stack ds-stack--row search-filters__group">
            <legend className="visually-hidden">{facet.label}</legend>
            {[...facet.values.entries()].map(([value, count]) => {
              const pressed = (params.filters[key] ?? []).includes(value);
              return (
                <Button
                  key={value}
                  variant={pressed ? "primary" : "secondary"}
                  aria-pressed={pressed}
                  onClick={() => toggleValue(key, value)}
                >
                  {value} ({count})
                </Button>
              );
            })}
          </fieldset>
        ) : null,
      )}
      {active ? (
        <Button variant="secondary" onClick={() => onChange({ ...params, kinds: [], filters: {} })}>
          {t("search:clearFilters")}
        </Button>
      ) : null}
    </fieldset>
  );
}
