import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { type Chart, type Content, useContents } from "./api";

const ICONS: Record<string, string> = {
  notice: "megaphone",
  stats: "chart",
  top: "trophy",
  movies: "film",
  series: "tv",
  books: "book",
  audiobooks: "headphones",
  games: "gamepad",
  music: "music",
  requests: "inbox",
  releases: "clapperboard",
  tv: "radio",
  upcoming: "calendar",
  articles: "newspaper",
};

/**
 * issue 323: what an edition tells, as options — each switched on or off, in the edition's order; « default »
 * brings the usual ones back.
 */
const CHART_ICONS: Record<string, string> = {
  figures: "sparkles",
  activity: "chart",
  kinds: "list",
  weekdays: "calendar",
  hours: "clock",
  genres: "tag",
};

export function ContentPicker({
  value,
  onChange,
  charts,
  onCharts,
}: {
  value: Content[] | null | undefined;
  onChange: (next: Content[]) => void;
  /** issue 324: the statistics' charts, shown while the statistics are on. */
  charts?: Chart[] | null | undefined;
  onCharts?: (next: Chart[]) => void;
}) {
  const t = useT();
  const offered = useContents();
  const all = offered.data?.contents ?? [];
  const chosen = value ?? offered.data?.defaults ?? [];
  const allCharts = offered.data?.charts ?? [];
  const drawn = charts ?? offered.data?.chart_defaults ?? [];
  return (
    <fieldset className="edition-contents">
      <legend>{t("news:edition.admin.contents")}</legend>
      <p className="admin-muted">{t("news:edition.admin.contentsHint")}</p>
      <div className="edition-contents__chips">
        {all.map((content) => {
          const checked = chosen.includes(content);
          return (
            <label key={content} className="edition-content" data-checked={checked || undefined}>
              <input
                type="checkbox"
                checked={checked}
                onChange={() => onChange(all.filter((c) => (c === content ? !checked : chosen.includes(c))))}
              />
              <Icon name={ICONS[content] ?? "sparkles"} size={14} />
              {t(`news:edition.content.${content}`)}
            </label>
          );
        })}
      </div>
      {onCharts && chosen.includes("stats") ? (
        // issue 324: which charts the statistics draw
        <div className="edition-contents__charts">
          <span className="admin-muted">{t("news:edition.admin.charts")}</span>
          <div className="edition-contents__chips">
            {allCharts.map((chart) => {
              const checked = drawn.includes(chart);
              return (
                <label key={chart} className="edition-content" data-checked={checked || undefined}>
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() =>
                      onCharts(allCharts.filter((c) => (c === chart ? !checked : drawn.includes(c))))
                    }
                  />
                  <Icon name={CHART_ICONS[chart] ?? "chart"} size={14} />
                  {t(`news:edition.chart.${chart}`)}
                </label>
              );
            })}
          </div>
        </div>
      ) : null}
      <button
        type="button"
        className="ds-button ds-button--ghost edition-contents__reset"
        onClick={() => {
          onChange(offered.data?.defaults ?? []);
          onCharts?.(offered.data?.chart_defaults ?? []);
        }}
      >
        <Icon name="sync" size={14} />
        {t("news:edition.admin.contentsDefault")}
      </button>
    </fieldset>
  );
}
