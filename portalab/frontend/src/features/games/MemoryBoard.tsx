import { Link as RouterLink } from "react-router";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import type { MediaCard } from "../cards/api";
import { MediaCardView } from "../cards/MediaCardView";
import { type MemoryFace, metadataImage, type SoloView, useSessionAction } from "./api";
import { Board } from "./Boards";

function Face({ face }: { face: MemoryFace }) {
  if (face.card) return <MediaCardView card={face.card as unknown as MediaCard} size="sm" />;
  return (
    <span className="games-tile__poster">
      <img src={metadataImage(face.poster, "w185") ?? ""} alt={face.title ?? ""} />
    </span>
  );
}

/**
 * Issue 265: the memory — my own cards (the library's posters when I own too few) laid face down by the
 * server, two turned over at a time: a pair found stays up, two that differ turn back at the next try.
 */
export function MemoryBoard({ view, onAgain }: { view: SoloView; onAgain: () => void }) {
  const t = useT();
  const act = useSessionAction(view.id);
  const board = view.board ?? [];
  const found = board.filter((tile) => tile.state === "matched").length / 2;
  const done = view.status === "done";
  return (
    <section className="games-memory">
      <div className="games-status">
        <span>{t("gamification:games.memory.found", { found, pairs: view.pairs ?? 0 })}</span>
        <b>{t("gamification:games.memory.moves", { moves: view.moves ?? 0 })}</b>
      </div>
      <ul className="games-memory__board" data-count={board.length}>
        {board.map((tile, at) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: a place on the board
          <li key={at}>
            <button
              type="button"
              className="games-tile"
              data-state={tile.state}
              disabled={done || tile.state === "matched" || act.isPending}
              aria-label={t("gamification:games.memory.tile", { place: at + 1 })}
              onClick={() => act.mutate({ kind: "flip", position: at })}
            >
              <span className="games-tile__back" aria-hidden="true">
                <Icon name="layers" size={28} />
              </span>
              <span className="games-tile__front">{tile.face ? <Face face={tile.face} /> : null}</span>
            </button>
          </li>
        ))}
      </ul>
      {done ? (
        <div className="games-over">
          <Icon name="trophy" size={40} />
          <h2>{t("gamification:games.score", { score: view.score })}</h2>
          <div className="games-actions">
            <Button onClick={onAgain}>
              <Icon name="retry" size={16} />
              {t("gamification:games.again")}
            </Button>
            <Button asChild variant="secondary">
              <RouterLink to="/games">{t("gamification:games.back")}</RouterLink>
            </Button>
          </div>
          <Board game="memory" />
        </div>
      ) : null}
    </section>
  );
}
