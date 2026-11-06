import { useQuery } from "@tanstack/react-query";
import { useId } from "react";
import { Link, Navigate, useSearchParams } from "react-router";
import { api } from "../../../api/client";
import { Icon } from "../../../design-system/components/Icon";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { AskDialog } from "../../requests/AskDialog";
import { useAskOptions } from "../../requests/api";
import type { AskStart } from "../../requests/RequestsPage";
import { GameFacts } from "../detail/DetailPage";
import { TitleHero } from "../detail/TitleHero";
import "../media.css";
import "../book/book.css";
import "./game.css";

/**
 * Issue 368: a game the library lacks, as the game database tells it (IGDB), laid out as a library game's
 * page — the same head (cover, artwork behind, facts, actions), its summary and facts (platforms, studios,
 * publisher, release, genres, themes, modes), its franchises, its screenshots and artworks; asking the team
 * for it on one of its platforms. The library's page opens instead when it has the game. Reached from a
 * franchise's page.
 */
interface Sheet {
  service: string;
  ref: string;
  title: string;
  summary: string | null;
  storyline: string | null;
  year: number | null;
  release_date: string | null;
  cover: string | null;
  backdrop: string | null;
  images: string[];
  genres: string[];
  themes: string[];
  modes: string[];
  platforms: string[];
  developers: string[];
  publishers: string[];
  franchises: { name: string; route: string | null }[];
  names: Record<string, string>;
  rating: number | null;
  votes: number;
  trailer: string | null;
  library: string | null;
}

function useGameSheet(service: string, ref: string) {
  return useQuery({
    queryKey: ["media", "game-sheet", service, ref],
    enabled: Boolean(service && ref),
    retry: false,
    staleTime: 10 * 60_000,
    queryFn: async () =>
      (await api.GET("/api/v1/media/game", { params: { query: { service, ref } } })).data as unknown as Sheet,
  });
}

/** Where a request for it begins: the game, its studio, its id there, the platform wanted. */
function askStart(game: Sheet, platform?: string): AskStart {
  return {
    kind: "game",
    title: game.title,
    creator: game.developers[0] ?? game.publishers[0],
    year: game.year,
    edition: platform ?? null,
    ids: { igdb: [game.ref] },
  };
}

export function GameSheetPage() {
  const t = useT();
  const format = useFormat();
  const headingId = useId();
  const [params] = useSearchParams();
  const service = params.get("service") ?? "";
  const ref = params.get("ref") ?? "";
  const sheet = useGameSheet(service, ref);
  const asks = useAskOptions();
  if (sheet.isPending && service && ref) return <FunctionalState state="loading" />;
  if (!sheet.data) {
    const missing = !service || !ref || (sheet.error instanceof ApiError && sheet.error.status === 404);
    return (
      <section aria-labelledby={headingId} className="media-book">
        <PageHeader titleId={headingId} level={2} icon="gamepad" title={t("media:game.title")} />
        {missing ? (
          <p className="ds-panel">{t("media:game.notFound")}</p>
        ) : (
          <FunctionalState state="unavailable" onRetry={() => sheet.refetch()} />
        )}
      </section>
    );
  }
  const game = sheet.data;
  // one page per title: the library's (same look, with playing it) when it has it
  if (game.library) return <Navigate to={`/media/${game.library}`} replace />;
  const canAsk = Boolean(asks.data?.kinds.includes("game"));
  const others = Object.values(game.names).filter((name) => name !== game.title);
  return (
    <article aria-labelledby={headingId} className="media-detail media-game">
      <TitleHero
        headingId={headingId}
        level={2}
        title={game.title}
        kind="game"
        poster={game.cover}
        backdrop={game.backdrop}
        facts={[
          game.year ? String(game.year) : null,
          t("media:kind.game"),
          game.rating !== null ? `★ ${format.number(game.rating)}` : null,
        ]}
        badges={<span className="media-person__absent">{t("media:game.absent")}</span>}
        primary={
          canAsk ? (
            <AskDialog
              start={askStart(game)}
              trigger={
                <button type="button" className="ds-button ds-button--primary">
                  <Icon name="plus" size={16} />
                  {t("media:ask.askIt")}
                </button>
              }
            />
          ) : null
        }
        secondary={
          game.trailer ? (
            <a
              className="ds-button ds-button--secondary"
              href={`https://www.youtube.com/watch?v=${encodeURIComponent(game.trailer)}`}
              target="_blank"
              rel="noreferrer noopener"
            >
              <Icon name="play" size={16} />
              {t("media:discover.trailer")}
            </a>
          ) : undefined
        }
      />
      <section className="media-enriched" aria-label={t("media:detail.section.info")}>
        {others.length ? <p className="media-enriched__tagline">{others.join(" · ")}</p> : null}
        {game.summary ? <p className="media-enriched__overview">{game.summary}</p> : null}
        {game.storyline ? <p>{game.storyline}</p> : null}
        <GameFacts
          data={{
            publisher: game.publishers[0] ?? null,
            people: [...game.developers, ...game.publishers],
            released: game.release_date,
            year: game.year,
            tags: [...game.genres, ...game.themes, ...game.modes],
          }}
        />
      </section>
      {game.franchises.length ? (
        <section className="media-enriched" aria-label={t("media:game.franchises")}>
          <div className="media-enriched__block">
            <h3>{t("media:game.franchises")}</h3>
            <ul className="media-book__series">
              {game.franchises.map((f) => (
                <li key={f.name}>{f.route ? <Link to={f.route}>{f.name}</Link> : f.name}</li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}
      {game.platforms.length ? (
        <section className="media-enriched" aria-label={t("media:game.platforms")}>
          <div className="media-enriched__block">
            <h3>{t("media:game.platforms")}</h3>
            <ul className="media-book__editions" aria-label={t("media:game.platforms")}>
              {game.platforms.map((platform) => (
                <li key={platform} className="media-game__platform">
                  <span className="media-book__edition-text">
                    <strong>{platform}</strong>
                  </span>
                  {canAsk ? (
                    <AskDialog
                      start={askStart(game, platform)}
                      trigger={
                        <button type="button" className="media-person__ask">
                          <Icon name="plus" size={14} />
                          {t("media:game.askOn", { platform })}
                        </button>
                      }
                    />
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}
      {game.images.length ? (
        <section className="media-enriched" aria-label={t("media:game.images")}>
          <div className="media-enriched__block">
            <h3>{t("media:game.images")}</h3>
            <ul className="media-game__images">
              {game.images.map((src) => (
                <li key={src}>
                  <img src={src} alt="" loading="lazy" />
                </li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}
      <p className="media-book__source">
        {t("media:game.source")}
        {game.votes ? ` ${t("media:game.votes", { count: game.votes })}.` : ""}
      </p>
    </article>
  );
}

export default GameSheetPage;
