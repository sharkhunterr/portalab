import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { useLocaleContext } from "../../i18n/provider/I18nProvider";
import { ApiError } from "../../state/regions";
import {
  beat,
  chooseFirmware,
  emulatorLanguage,
  endSitting,
  type Sitting,
  startSitting,
  useRetroGame,
} from "./api";
import "../media/player/player.css";
import "./retro.css";

type Emulator = {
  pause?: (silent?: boolean) => void;
  gameManager?: { saveSaveFiles?: () => void };
};
type EmulatorWindow = Window & Record<string, unknown> & { EJS_emulator?: Emulator };
type Stage = "ready" | "starting" | "playing" | "over";

/** Leaving the game reloads the title's page: the portal's stricter policy comes back with it. */
function leave(objectId: string) {
  window.location.assign(`/media/${objectId}`);
}

function emulator(): Emulator | undefined {
  return (window as unknown as EmulatorWindow).EJS_emulator;
}

/** The game's own saves written down before the page goes (they stay in this browser). */
function keepSaves() {
  try {
    emulator()?.gameManager?.saveSaveFiles?.();
  } catch {
    // nothing to keep: the game had not started
  }
}

let launched = false; // EmulatorJS's settings are the page's globals: one game per page load

/** RomM's EmulatorJS, as RomM starts it: the core of the game's platform, its file, its firmware. */
function launch(sitting: Sitting, language: string, onStart: () => void) {
  if (launched) return;
  launched = true;
  const w = window as unknown as EmulatorWindow;
  w.EJS_player = "#retro-game";
  w.EJS_core = sitting.game.core;
  w.EJS_gameUrl = sitting.game_url;
  w.EJS_gameName = sitting.game.title;
  w.EJS_pathtodata = sitting.emulator_path;
  const bios = chooseFirmware(sitting);
  if (bios) w.EJS_biosUrl = bios;
  w.EJS_threads = sitting.game.threads && window.crossOriginIsolated;
  w.EJS_startOnLoaded = true;
  w.EJS_disableDatabases = true; // each sitting's address is its own: nothing to find again in a cache
  w.EJS_language = language;
  w.EJS_disableAutoLang = true;
  w.EJS_onGameStart = onStart;
  const script = document.createElement("script");
  script.src = `${sitting.emulator_path}loader.js`;
  script.async = true;
  document.body.appendChild(script);
}

function reasonOf(error: unknown): string {
  const code = error instanceof ApiError ? error.code : undefined;
  if (code === "retro.disabled") return "disabled";
  if (code === "retro.not_playable") return "nothing";
  if (code === "household.screen_time_up") return "screen";
  if (code === "household.restricted" || (error instanceof ApiError && error.status === 403))
    return "restricted";
  return "unavailable";
}

/**
 * ``/media/:objectId/play`` (issue 419): a library's game over the whole window, in the library's own
 * emulator — a page of its own, entered by a full load (its policy lets the emulator compile and run its
 * cores). The sitting starts with « Play », is kept alive while the game runs and ends when the page goes;
 * a household profile's screen time ends it once spent.
 */
export function RetroPage() {
  const t = useT();
  const { objectId = "" } = useParams();
  const { language } = useLocaleContext();
  const game = useRetroGame(objectId);
  const [sitting, setSitting] = useState<Sitting | null>(null);
  const [stage, setStage] = useState<Stage>("ready");
  const [failure, setFailure] = useState<string | null>(null);
  const [left, setLeft] = useState<number | null>(null);
  const current = useRef<string | null>(null);

  useEffect(() => {
    document.documentElement.dataset.playing = "true"; // the shell steps aside
    return () => {
      delete document.documentElement.dataset.playing;
    };
  }, []);

  const finish = useCallback(() => {
    keepSaves();
    if (current.current) {
      void endSitting(current.current);
      current.current = null;
    }
  }, []);

  useEffect(() => {
    window.addEventListener("pagehide", finish);
    return () => window.removeEventListener("pagehide", finish);
  }, [finish]);

  const start = async () => {
    setStage("starting");
    try {
      const started = await startSitting(objectId);
      current.current = started.id;
      setSitting(started);
      launch(started, emulatorLanguage(language), () => setStage("playing"));
    } catch (error) {
      setFailure(reasonOf(error));
      setStage("ready");
    }
  };

  useEffect(() => {
    if (!sitting || stage !== "playing") return;
    const timer = window.setInterval(() => {
      if (document.visibilityState !== "visible") return; // a hidden tab does not count
      beat(sitting.id)
        .then((answer) => {
          setLeft(answer.minutes_left ?? null);
          if (answer.stop) {
            emulator()?.pause?.(true);
            finish();
            setStage("over");
          }
        })
        .catch(() => undefined); // a beat missed is caught up by the next one
    }, sitting.heartbeat_s * 1000);
    return () => window.clearInterval(timer);
  }, [sitting, stage, finish]);

  const quit = () => {
    finish();
    leave(objectId);
  };

  if (game.isPending) {
    return (
      <div className="retro-page" data-state="loading">
        <div className="player-spinner" role="status" aria-label={t("retro:loading")} />
      </div>
    );
  }
  const reason = failure ?? (game.isError || !game.data ? reasonOf(game.error) : null);
  if (reason || !game.data) {
    return (
      <div className="retro-page" data-state="error">
        <div className="player-failure retro-failure" role="alert">
          <Icon name="joystick" size={28} />
          <p>{t(`retro:error.${reason ?? "unavailable"}`)}</p>
          <div>
            {reason === "unavailable" ? (
              <button
                type="button"
                className="player-pill"
                data-primary
                onClick={() => {
                  setFailure(null);
                  void game.refetch();
                }}
              >
                {t("retro:retry")}
              </button>
            ) : null}
            <button type="button" className="player-pill" onClick={() => leave(objectId)}>
              {t("retro:back")}
            </button>
          </div>
        </div>
      </div>
    );
  }
  const info = game.data;
  return (
    <div className="retro-page" data-stage={stage}>
      <header className="retro-bar">
        <button type="button" className="player-icon retro-icon" onClick={quit} aria-label={t("retro:quit")}>
          <Icon name="chevron-left" size={22} />
        </button>
        <div className="retro-bar__title">
          <strong>{info.title}</strong>
          <small>
            {info.service_name
              ? t("retro:platform", { platform: info.platform.toUpperCase(), service: info.service_name })
              : info.platform.toUpperCase()}
          </small>
        </div>
        {left !== null ? (
          <span className="retro-left" role="status">
            {t("retro:left", { count: left })}
          </span>
        ) : null}
      </header>
      <main className="retro-stage">
        <div id="retro-game" className="retro-game" />
        {stage === "ready" || stage === "starting" ? (
          <div className="retro-start">
            <Icon name="joystick" size={40} />
            <p>{t("retro:intro", { title: info.title })}</p>
            <button
              type="button"
              className="player-pill"
              data-primary
              disabled={stage === "starting"}
              onClick={() => void start()}
            >
              {t(stage === "starting" ? "retro:starting" : "retro:play")}
            </button>
            {info.threads && !window.crossOriginIsolated ? (
              <small className="retro-hint">{t("retro:threads")}</small>
            ) : null}
          </div>
        ) : null}
        {stage === "over" ? (
          <div className="retro-start" role="alert">
            <Icon name="clock" size={40} />
            <p>{t("retro:error.screen")}</p>
            <button type="button" className="player-pill" data-primary onClick={() => leave(objectId)}>
              {t("retro:back")}
            </button>
          </div>
        ) : null}
      </main>
    </div>
  );
}

export default RetroPage;
