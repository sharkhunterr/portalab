import { useState } from "react";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { useBoard } from "./api";

const PERIODS = ["week", "month", "all"] as const;

/** Issue 265: a game's board — each member's best score (the parties won, the challenges completed). */
export function Board({ game, title }: { game: string; title?: string }) {
  const t = useT();
  const format = useFormat();
  const [period, setPeriod] = useState<(typeof PERIODS)[number]>("week");
  const board = useBoard(game, period);
  const entries = board.data?.entries ?? [];
  return (
    <section className="games-board" aria-label={title ?? t("gamification:games.board")}>
      <header>
        <h3>
          <Icon name="trophy" size={16} />
          {title ?? t("gamification:games.board")}
        </h3>
        <fieldset className="games-periods" aria-label={t("gamification:games.period")}>
          {PERIODS.map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={period === value}
              onClick={() => setPeriod(value)}
            >
              {t(`gamification:games.periods.${value}`)}
            </button>
          ))}
        </fieldset>
      </header>
      {entries.length ? (
        <ol>
          {entries.map((entry) => (
            <li key={`${entry.rank}:${entry.name}`} data-me={entry.me || undefined}>
              <span className="games-board__rank">{entry.rank}</span>
              <span>{entry.name}</span>
              <b>{format.number(entry.value)}</b>
            </li>
          ))}
          {board.data?.me && !entries.some((e) => e.me) ? (
            <li data-me>
              <span className="games-board__rank">{board.data.me.rank}</span>
              <span>{t("gamification:games.you")}</span>
              <b>{format.number(board.data.me.value)}</b>
            </li>
          ) : null}
        </ol>
      ) : (
        <p className="games-muted">{t("gamification:games.boardEmpty")}</p>
      )}
    </section>
  );
}
