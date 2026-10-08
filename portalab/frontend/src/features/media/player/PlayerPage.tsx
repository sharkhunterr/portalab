import { useCallback, useEffect } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { usePlayerInfo } from "./api";
import { VideoPlayer } from "./VideoPlayer";
import "./player.css";

/**
 * ``/media/:objectId/watch`` (027, #2): the player over the whole window — a title, or one episode of it
 * (``?item=``, when moving to the next one). Leaving goes back to the title's page.
 */
export function PlayerPage() {
  const t = useT();
  const navigate = useNavigate();
  const { objectId = "" } = useParams();
  const [search, setSearch] = useSearchParams();
  const item = search.get("item");
  const info = usePlayerInfo(objectId, item);
  const exit = useCallback(() => navigate(`/media/${objectId}`), [navigate, objectId]);
  const episode = useCallback((next: string) => setSearch({ item: next }, { replace: true }), [setSearch]);

  useEffect(() => {
    document.documentElement.dataset.playing = "true"; // the shell steps aside (scrollbars, ambient)
    return () => {
      delete document.documentElement.dataset.playing;
    };
  }, []);

  if (info.isPending) {
    return (
      <div className="player-page" data-state="loading">
        <div className="player-spinner" role="status" aria-label={t("media:player.loading")} />
      </div>
    );
  }
  if (info.isError || !info.data) {
    const code = info.error instanceof ApiError ? info.error.code : undefined;
    const reason =
      code === "media.player_unlinked"
        ? "unlinked"
        : code === "media.player_disabled"
          ? "disabled"
          : code === "media.player_denied"
            ? "denied"
            : code === "media.player_nothing"
              ? "nothing"
              : "unavailable";
    return (
      <div className="player-page" data-state="error">
        <div className="player-failure" role="alert">
          <Icon name={reason === "unlinked" ? "link" : "alert"} size={28} />
          <p>{t(`media:player.page.${reason}`)}</p>
          <div>
            {reason === "unlinked" ? (
              <Link className="player-pill" data-primary to="/settings/media-accounts">
                <Icon name="link" size={18} />
                {t("media:player.page.link")}
              </Link>
            ) : reason === "unavailable" ? (
              <button type="button" className="player-pill" data-primary onClick={() => info.refetch()}>
                <Icon name="sync" size={18} />
                {t("media:player.retry")}
              </button>
            ) : null}
            <button type="button" className="player-pill" onClick={exit}>
              {t("media:player.back")}
            </button>
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="player-page">
      <VideoPlayer
        key={info.data.item.external_id}
        objectId={objectId}
        info={info.data}
        onExit={exit}
        onEpisode={episode}
      />
    </div>
  );
}

export default PlayerPage;
