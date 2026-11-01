import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { type Content, useContents } from "./api";

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
export function ContentPicker({
  value,
  onChange,
}: {
  value: Content[] | null | undefined;
  onChange: (next: Content[]) => void;
}) {
  const t = useT();
  const offered = useContents();
  const all = offered.data?.contents ?? [];
  const chosen = value ?? offered.data?.defaults ?? [];
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
      <button
        type="button"
        className="ds-button ds-button--ghost edition-contents__reset"
        onClick={() => onChange(offered.data?.defaults ?? [])}
      >
        <Icon name="sync" size={14} />
        {t("news:edition.admin.contentsDefault")}
      </button>
    </fieldset>
  );
}
