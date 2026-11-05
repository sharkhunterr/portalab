import { Link as RouterLink } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { useLocaleContext } from "../../i18n/provider/I18nProvider";
import { imageUrl } from "../media/api";
import { type BingoCell, useBingo } from "./api";

/**
 * Issue 356: the month's media bingo on the games page — the same card for every member; a square ticks
 * itself when I finish a title that fits it (its poster stamped on it), a line lights up when complete, the
 * full card is the jackpot. A new card each month.
 */
const ICONS: Record<string, string> = {
  "genre:comedy": "laugh",
  "genre:drama": "drama",
  "genre:action": "bomb",
  "genre:horror": "skull",
  "genre:scifi": "rocket",
  "genre:animation": "sparkles",
  "genre:thriller": "eye",
  "genre:crime": "fingerprint",
  "genre:romance": "heart",
  "genre:fantasy": "wand",
  "genre:mystery": "search",
  "genre:family": "users",
  "genre:war": "swords",
  "genre:history": "landmark",
  "genre:documentary": "camera",
  "genre:music": "music",
  "genre:adventure": "compass",
  "genre:western": "mountain",
  "era:before1970": "hourglass",
  "era:recent": "sparkle",
  "length:long": "clock",
  "length:short": "zap",
  "series:pilot": "circle-play",
  "series:marathon": "flame",
  "kind:book": "book",
  "kind:comics": "brush",
  "kind:audiobook": "headphones",
  "kind:game": "gamepad",
  "kind:live": "tv",
  "kind:radio": "radio",
  review: "star",
  later: "bookmark",
};
const GROUP_ICONS: Record<string, string> = { era: "calendar", country: "globe" };

function useCellLabel() {
  const t = useT();
  const { locale } = useLocaleContext();
  return (key: string) => {
    const [head, value] = key.split(":");
    if (head === "country" && value) {
      let country = value;
      try {
        country = new Intl.DisplayNames([locale], { type: "region" }).of(value) ?? value;
      } catch {
        // an unknown code: the code itself
      }
      return t("gamification:games.bingo.cell.country", { country });
    }
    return t(`gamification:games.bingo.cell.${key.replace(":", ".")}`);
  };
}

function Square({ cell, lit, label }: { cell: BingoCell; lit: boolean; label: string }) {
  const t = useT();
  const icon = ICONS[cell.key] ?? GROUP_ICONS[cell.group] ?? "target";
  const poster = cell.by?.image_id ? imageUrl(cell.by.image_id) : null;
  return (
    <li
      className="games-bingo__square"
      data-group={cell.group}
      data-ticked={cell.by ? true : undefined}
      data-lit={lit || undefined}
    >
      {poster ? <img className="games-bingo__poster" src={poster} alt="" loading="lazy" /> : null}
      <span className="games-bingo__icon" aria-hidden="true">
        <Icon name={icon} size={22} />
      </span>
      <span className="games-bingo__label">{label}</span>
      {cell.by ? (
        <>
          <span className="games-bingo__stamp" aria-hidden="true">
            <Icon name="check" size={20} />
          </span>
          {cell.by.id ? (
            <RouterLink className="games-bingo__by" to={`/media/${cell.by.id}`}>
              <span className="visually-hidden">{t("gamification:games.bingo.ticked")} </span>
              {cell.by.title}
            </RouterLink>
          ) : (
            <span className="games-bingo__by">
              <span className="visually-hidden">{t("gamification:games.bingo.ticked")} </span>
              {cell.by.title}
            </span>
          )}
        </>
      ) : (
        <span className="visually-hidden">{t("gamification:games.bingo.open")}</span>
      )}
    </li>
  );
}

export function BingoSection() {
  const t = useT();
  const format = useFormat();
  const { locale } = useLocaleContext();
  const label = useCellLabel();
  const bingo = useBingo();
  const data = bingo.data;
  if (!data?.cells?.length) return null;
  const lit = new Set(data.lines.filter((line) => line.done).flatMap((line) => line.cells));
  const month = new Date(`${data.month}T12:00:00Z`);
  const total = data.cells.length;
  return (
    <section
      className="games-bingo"
      aria-labelledby="games-bingo"
      data-card={data.card || undefined}
      data-size={data.size}
    >
      <header className="games-bingo__head">
        <span className="games-bingo__art" aria-hidden="true">
          <Icon name="blocks" size={30} />
        </span>
        <div>
          <h2 id="games-bingo">
            {t("gamification:games.bingo.title", {
              month: month.toLocaleDateString(locale, { month: "long", timeZone: "UTC" }),
            })}
          </h2>
          <p className="games-muted">{t("gamification:games.bingo.pitch")}</p>
        </div>
        <dl className="games-bingo__figures">
          <div>
            <dt>{t("gamification:games.bingo.squares")}</dt>
            <dd>
              {data.squares}/{total}
            </dd>
          </div>
          <div>
            <dt>{t("gamification:games.bingo.lines")}</dt>
            <dd>{data.done_lines}</dd>
          </div>
        </dl>
      </header>
      {data.card ? (
        <p className="games-bingo__jackpot" role="status">
          <Icon name="trophy" size={18} />
          {t("gamification:games.bingo.jackpot")}
        </p>
      ) : null}
      <ol
        className="games-bingo__grid"
        aria-label={t("gamification:games.bingo.grid", { squares: data.squares, total })}
      >
        {data.cells.map((cell, index) => (
          <Square key={cell.key} cell={cell} lit={lit.has(index)} label={label(cell.key)} />
        ))}
      </ol>
      <p className="games-bingo__foot games-muted">
        {t("gamification:games.bingo.how")}{" "}
        {t("gamification:games.bingo.until", { until: format.date(data.ends_at) })}{" "}
        {data.players
          ? t("gamification:games.bingo.others", { count: data.players, cards: data.cards })
          : null}
      </p>
    </section>
  );
}
