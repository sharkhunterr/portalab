import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { useLocaleContext } from "../../i18n/provider/I18nProvider";
import { ApiError } from "../../state/regions";
import {
  beat,
  chooseFirmware,
  dropState,
  type EmulatorPreferences,
  emulatorLanguage,
  endSitting,
  fetchPreferences,
  fetchSaves,
  keepPreferences,
  type Progress,
  type Sitting,
  startSitting,
  useRetroGame,
} from "./api";
import { LoadingSteps } from "./LoadingSteps";
import { type StepKey, useEmulatorLoading } from "./loading";
import { entriesOf, keyOf, RomChooser, romsOf, SaveChooser } from "./Resume";
import { emulator, picture, SaveKeeper } from "./saves";
import "../media/player/player.css";
import "./retro.css";

type Stage = "ready" | "starting" | "playing" | "over";
const QUIT_WAIT_MS = 8000; // the most the page waits for its saves when the member leaves

/** Leaving the game reloads the title's page: the portal's stricter policy comes back with it. */
function leave(objectId: string) {
  window.location.assign(`/media/${objectId}`);
}

type Hooks = {
  start(): void;
  ready(): void;
  saveState(state: Uint8Array): void;
  loadState(): void;
  saveSave(save: Uint8Array | null): void;
  loadSave(): void;
};

const LOADER = "script[data-retro-loader]"; // EmulatorJS's settings are the page's globals: one game a load

/**
 * RomM's EmulatorJS, as RomM starts it: the core of the game's platform, its file, its firmware — and,
 * issue 420, the saves taken over (the emulator's own save and load buttons go to the portal's slots).
 */
function launch(sitting: Sitting, language: string, hooks: Hooks, preferences: EmulatorPreferences | null) {
  if (document.querySelector(LOADER)) return;
  if (sitting.game.engine === "ruffle") {
    launchRuffle(sitting, hooks);
    return;
  }
  const w = window as unknown as Record<string, unknown>;
  w.EJS_player = "#retro-game";
  w.EJS_core = sitting.game.core;
  w.EJS_gameUrl = sitting.game_url;
  w.EJS_gameName = sitting.game.title;
  w.EJS_pathtodata = sitting.emulator_path;
  const bios = chooseFirmware(sitting);
  if (bios) w.EJS_biosUrl = bios;
  if (sitting.state_url) w.EJS_loadStateURL = sitting.state_url; // « Continue »
  w.EJS_threads = sitting.game.threads && window.crossOriginIsolated;
  w.EJS_startOnLoaded = true;
  w.EJS_disableDatabases = true; // each sitting's address is its own: nothing to find again in a cache
  // the game's own save written every minute; 421: the member's own options and controls for this core
  w.EJS_defaultOptions = { "save-save-interval": "60", ...(preferences?.settings ?? {}) };
  if (preferences?.controlSettings) w.EJS_defaultControls = preferences.controlSettings;
  if (sitting.game.control_scheme) w.EJS_controlScheme = sitting.game.control_scheme; // a Sega console's pad
  w.EJS_language = language;
  w.EJS_disableAutoLang = true;
  w.EJS_onGameStart = hooks.start;
  w.EJS_ready = hooks.ready;
  w.EJS_onSaveState = (event: { state?: Uint8Array }) => event.state && hooks.saveState(event.state);
  w.EJS_onLoadState = hooks.loadState;
  w.EJS_onSaveSave = (event: { save?: Uint8Array | null }) => hooks.saveSave(event.save ?? null);
  w.EJS_onLoadSave = hooks.loadSave;
  const script = document.createElement("script");
  script.src = `${sitting.emulator_path}loader.js`;
  script.async = true;
  script.dataset.retroLoader = "true";
  document.body.appendChild(script);
}

type RuffleWindow = {
  RufflePlayer?: {
    config?: Record<string, unknown>;
    newest?: () => {
      createPlayer: () => HTMLElement & { load: (options: Record<string, unknown>) => unknown };
    };
  };
};

/** 421: a Flash game in Ruffle, as RomM serves it (its files relayed by the portal). */
function launchRuffle(sitting: Sitting, hooks: Hooks) {
  const w = window as unknown as RuffleWindow;
  w.RufflePlayer = {
    ...(w.RufflePlayer ?? {}),
    config: { publicPath: sitting.emulator_path, polyfills: false },
  };
  const script = document.createElement("script");
  script.src = `${sitting.emulator_path}ruffle.js`;
  script.async = true;
  script.dataset.retroLoader = "true";
  script.onload = () => {
    const stage = document.getElementById("retro-game");
    const player = w.RufflePlayer?.newest?.()?.createPlayer();
    if (!stage || !player) return;
    player.style.width = "100%";
    player.style.height = "100%";
    stage.appendChild(player);
    void player.load({
      url: sitting.game_url,
      publicPath: sitting.emulator_path,
      autoplay: "on",
      allowFullScreen: true,
      letterbox: "on",
      forceScale: true,
      openUrlMode: "confirm",
      unmuteOverlay: "hidden",
    });
    hooks.start();
  };
  document.body.appendChild(script);
}

/** 421: the controls and options the member set during the game, as the emulator holds them. */
function preferencesNow(): EmulatorPreferences | null {
  const e = emulator();
  if (!e?.controls && !e?.settings) return null;
  return { controlSettings: e.controls, ...(e.settings ? { settings: e.settings } : {}) };
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
 * cores). The sitting starts with « Play » (or « Continue », from the latest save state — issue 420), is kept
 * alive while the game runs and ends when the page goes; a household profile's screen time ends it once spent.
 * The game's own save follows the member; states go to slots; leaving keeps where the game was.
 */
export function RetroPage() {
  const t = useT();
  const format = useFormat();
  const { objectId = "" } = useParams();
  const [params] = useSearchParams();
  const { language } = useLocaleContext();
  const game = useRetroGame(objectId);
  const [sitting, setSitting] = useState<Sitting | null>(null);
  const [stage, setStage] = useState<Stage>("ready");
  const [failure, setFailure] = useState<string | null>(null);
  const [left, setLeft] = useState<number | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [panel, setPanel] = useState(false);
  const [slot, setSlot] = useState(1);
  const [notice, setNotice] = useState<string | null>(null);
  const [leaving, setLeaving] = useState(false);
  const [choice, setChoice] = useState<string | null | undefined>(undefined); // 420: the save to resume
  const [romChoice, setRomChoice] = useState<string | null>(null); // the copy to start a new game with
  const [fresh, setFresh] = useState<boolean | null>(null); // a new game asked here
  const [resumed, setResumed] = useState<number | null>(null);
  const current = useRef<string | null>(null);
  const keeper = useRef<SaveKeeper | null>(null);
  const active = useRef(1);
  active.current = slot;
  const preferred = useRef<string | null>(null); // 421: the settings the game started with
  const reopening = useRef(false); // a sitting closed under the page, opened again

  useEffect(() => {
    document.documentElement.dataset.playing = "true"; // the shell steps aside
    return () => {
      delete document.documentElement.dataset.playing;
    };
  }, []);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 3000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const refresh = useCallback(() => {
    if (current.current) void fetchSaves(current.current).then(setProgress, () => undefined);
  }, []);

  /** The sitting ends: the game's own save last sent (as much as a page going away may send), and the
   * controls and options the member changed. */
  const finish = useCallback(
    (goingAway = false) => {
      if (goingAway) void keeper.current?.keepSram(keeper.current.currentSram(), true);
      const now = preferencesNow();
      const core = sitting?.game.core;
      if (now && core && sitting?.game.engine !== "ruffle" && JSON.stringify(now) !== preferred.current) {
        preferred.current = JSON.stringify(now);
        void keepPreferences(core, now).catch(() => undefined);
      }
      if (current.current) {
        void endSitting(current.current);
        current.current = null;
      }
    },
    [sitting],
  );

  useEffect(() => {
    const away = () => finish(true);
    window.addEventListener("pagehide", away);
    return () => window.removeEventListener("pagehide", away);
  }, [finish]);

  /** Where the game is, kept in slot 0 with the game's own save (« Continue » starts there). */
  const keepPlace = useCallback(async () => {
    const saves = keeper.current;
    if (!saves) return;
    await Promise.race([
      Promise.allSettled([saves.keepSram(saves.currentSram()), saves.saveCurrent(0)]),
      new Promise((resolve) => window.setTimeout(resolve, QUIT_WAIT_MS)),
    ]);
  }, []);

  const saveTo = async (target: number) => {
    setSlot(target);
    const ok = await keeper.current?.saveCurrent(target);
    setNotice(t(ok ? "retro:saves.saved" : "retro:saves.failed", { slot: target }));
    refresh();
  };

  const loadFrom = async (target: number) => {
    setSlot(target || active.current);
    const ok = await keeper.current?.loadState(target);
    setNotice(t(ok ? "retro:saves.loaded" : "retro:saves.failed", { slot: target }));
    if (ok) setPanel(false);
  };

  const remove = async (target: number) => {
    if (!current.current) return;
    await dropState(current.current, target).catch(() => undefined);
    refresh();
  };

  const start = async (resume: number | null, rom: string | null = null) => {
    setResumed(resume);
    setStage("starting");
    try {
      const started = await startSitting(objectId, resume, rom);
      current.current = started.id;
      const saves = new SaveKeeper(started);
      keeper.current = saves;
      setSitting(started);
      setProgress(game.data?.progress ?? null);
      const sram = Boolean(game.data?.progress?.sram_at);
      const preferences =
        started.game.engine === "ruffle" ? null : await fetchPreferences(started.game.core).catch(() => null);
      preferred.current = preferences ? JSON.stringify(preferences) : null;
      launch(
        started,
        emulatorLanguage(language),
        {
          start: () => {
            setStage("playing");
            // a state carries the game's own save: it is loaded only for a new game
            if (sram && !started.state_url) void saves.loadSram();
          },
          ready: () =>
            emulator()?.on?.("saveSaveFiles", (data) => void saves.keepSram(data as Uint8Array | null)),
          saveState: (state) => {
            const target = active.current;
            void picture()
              .then((shot) => saves.keepState(target, state, shot))
              .then((ok) => {
                setNotice(t(ok ? "retro:saves.saved" : "retro:saves.failed", { slot: target }));
                refresh();
              });
          },
          loadState: () => void loadFrom(active.current),
          saveSave: (save) => void saves.keepSram(save),
          loadSave: () => void saves.loadSram(),
        },
        preferences,
      );
    } catch (error) {
      setFailure(reasonOf(error));
      setStage("ready");
    }
  };

  useEffect(() => {
    if (!sitting || stage !== "playing") return;
    const timer = window.setInterval(() => {
      // a page in the background still says it is there (its time is not counted): its sitting stays open
      beat(sitting.id, document.visibilityState === "visible")
        .then(async (answer) => {
          setLeft(answer.minutes_left ?? null);
          if (answer.stop) {
            await keepPlace(); // the screen pictured while the game still runs (paused, it is black)
            emulator()?.pause?.(true);
            finish();
            setStage("over");
          }
        })
        .catch((error: unknown) => {
          // the sitting was closed meanwhile (the page frozen too long in the background): the game goes on
          // in a new one — its time counted again — without starting the game again
          if (error instanceof ApiError && error.code === "retro.sitting_not_found" && !reopening.current) {
            reopening.current = true;
            startSitting(objectId, null, sitting.game.rom ?? null)
              .then((again) => {
                current.current = again.id;
                keeper.current = new SaveKeeper(again);
                setSitting(again);
              })
              .catch(() => undefined)
              .finally(() => {
                reopening.current = false;
              });
          }
          // any other missed beat is caught up by the next one
        });
    }, sitting.heartbeat_s * 1000);
    return () => window.clearInterval(timer);
  }, [sitting, stage, finish, keepPlace, objectId]);

  const quit = async () => {
    if (stage === "playing" && sitting?.game.engine !== "ruffle") {
      setLeaving(true);
      await keepPlace(); // the screen pictured while the game still runs (paused, it is black)
      emulator()?.pause?.(true);
    }
    finish();
    leave(objectId);
  };

  // 420: the loading, step by step — EmulatorJS's own progress, read from its screen
  const tracked = useEmulatorLoading(stage === "starting" && sitting !== null);

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
  const entries = entriesOf(info);
  const roms = romsOf(info);
  const askedRom = params.get("rom");
  const asked =
    params.get("resume") !== null ? `${askedRom ?? entries[0]?.rom}:${params.get("resume")}` : null;
  const wanted = entries.find((e) => keyOf(e) === asked) ?? entries[0] ?? null;
  const chosenKey = choice !== undefined ? choice : wanted ? keyOf(wanted) : null;
  const chosen = entries.find((e) => keyOf(e) === chosenKey) ?? null;
  const fresher = fresh ?? (Boolean(params.get("new")) || !entries.length);
  const rom = romChoice ?? (roms.some((r) => r.id === askedRom) ? askedRom : (roms[0]?.id ?? null));
  const ruffle = info.engine === "ruffle";
  const steps: StepKey[] = ruffle
    ? ["sitting", "emulator", "start"]
    : [
        "sitting",
        "emulator",
        "core",
        ...(sitting?.firmware.length ? (["bios"] as const) : []),
        "game",
        ...(resumed !== null ? (["state"] as const) : []),
        "start",
      ];
  const reached: StepKey = !sitting
    ? "sitting"
    : tracked.loading && steps.includes(tracked.loading.key)
      ? tracked.loading.key
      : "emulator";
  return (
    <div className="retro-page" data-stage={stage}>
      <header className="retro-bar">
        <button
          type="button"
          className="player-icon retro-icon"
          onClick={() => void quit()}
          disabled={leaving}
          aria-label={t("retro:quit")}
        >
          <Icon name="chevron-left" size={22} />
        </button>
        <div className="retro-bar__title">
          <strong>{info.title}</strong>
          <small>
            {leaving
              ? t("retro:saves.leaving")
              : info.service_name
                ? t("retro:platform", { platform: info.platform.toUpperCase(), service: info.service_name })
                : info.platform.toUpperCase()}
          </small>
        </div>
        {left !== null ? (
          <span className="retro-left" role="status">
            {t("retro:left", { count: left })}
          </span>
        ) : null}
        {stage === "playing" && sitting?.game.engine !== "ruffle" ? (
          <button
            type="button"
            className="player-icon retro-icon"
            aria-pressed={panel}
            aria-label={t("retro:saves.title")}
            title={t("retro:saves.title")}
            onClick={() => setPanel((open) => !open)}
          >
            <Icon name="floppy" size={20} />
          </button>
        ) : null}
      </header>
      <main className="retro-stage">
        <div id="retro-game" className="retro-game" />
        {notice ? (
          <p className="retro-notice" role="status">
            {notice}
          </p>
        ) : null}
        {panel && sitting && keeper.current ? (
          <SavesPanel
            keeper={keeper.current}
            progress={progress}
            active={slot}
            onSave={(target) => void saveTo(target)}
            onLoad={(target) => void loadFrom(target)}
            onDelete={(target) => void remove(target)}
            onClose={() => setPanel(false)}
            when={(value) => format.dateTime(value)}
          />
        ) : null}
        {stage === "ready" ? (
          <div className="retro-start">
            <Icon name="joystick" size={40} />
            <p>{t("retro:intro", { title: info.title })}</p>
            {!fresher ? (
              <>
                <small className="retro-hint">{t("retro:resume.choose")}</small>
                <SaveChooser
                  objectId={objectId}
                  entries={entries}
                  selected={chosen ? keyOf(chosen) : null}
                  onSelect={(entry) => setChoice(keyOf(entry))}
                  label={t("retro:resume.choose")}
                  copies={roms.length > 1}
                />
                <div className="retro-start__actions">
                  <button
                    type="button"
                    className="player-pill"
                    data-primary
                    disabled={!chosen}
                    onClick={() => chosen && void start(chosen.slot, chosen.rom)}
                  >
                    {t("retro:continue")}
                  </button>
                  <button type="button" className="player-pill" onClick={() => setFresh(true)}>
                    {t("retro:newGame")}
                  </button>
                </div>
              </>
            ) : (
              <>
                {roms.length > 1 ? (
                  <>
                    <small className="retro-hint">{t("retro:roms.choose")}</small>
                    <RomChooser
                      roms={roms}
                      selected={rom}
                      onSelect={setRomChoice}
                      label={t("retro:roms.choose")}
                    />
                  </>
                ) : null}
                <div className="retro-start__actions">
                  <button
                    type="button"
                    className="player-pill"
                    data-primary
                    onClick={() => void start(null, rom)}
                  >
                    {t(entries.length ? "retro:newGame" : "retro:play")}
                  </button>
                  {entries.length ? (
                    <button type="button" className="player-pill" onClick={() => setFresh(false)}>
                      {t("retro:resume.back")}
                    </button>
                  ) : null}
                </div>
              </>
            )}
            {info.threads && !window.crossOriginIsolated ? (
              <small className="retro-hint">{t("retro:threads")}</small>
            ) : null}
          </div>
        ) : null}
        {stage === "starting" ? (
          <div className="retro-start" role="status">
            {tracked.error ? (
              <>
                <Icon name="warning" size={36} />
                <p className="retro-start__error">{t("retro:loading.failed", { reason: tracked.error })}</p>
                <div className="retro-start__actions">
                  <button
                    type="button"
                    className="player-pill"
                    data-primary
                    onClick={() => window.location.reload()}
                  >
                    {t("retro:retry")}
                  </button>
                  <button type="button" className="player-pill" onClick={() => leave(objectId)}>
                    {t("retro:back")}
                  </button>
                </div>
              </>
            ) : (
              <>
                <p>{t(resumed !== null ? "retro:loading.resuming" : "retro:loading.title")}</p>
                <LoadingSteps steps={steps} current={reached} loading={tracked.loading} core={info.core} />
              </>
            )}
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

/** Issue 420: the slots — where the game was left (0) and the member's own (1…), with the screen's picture. */
function SavesPanel({
  keeper,
  progress,
  active,
  onSave,
  onLoad,
  onDelete,
  onClose,
  when,
}: {
  keeper: SaveKeeper;
  progress: Progress | null;
  active: number;
  onSave(slot: number): void;
  onLoad(slot: number): void;
  onDelete(slot: number): void;
  onClose(): void;
  when(value: string): string;
}) {
  const t = useT();
  const count = progress?.slots ?? 5;
  const slots = Array.from({ length: count + 1 }, (_, i) => i);
  return (
    <aside className="retro-saves" aria-label={t("retro:saves.title")}>
      <header className="retro-saves__head">
        <h2>{t("retro:saves.title")}</h2>
        <button
          type="button"
          className="player-icon retro-icon"
          onClick={onClose}
          aria-label={t("retro:saves.close")}
        >
          <Icon name="close" size={20} />
        </button>
      </header>
      <p className="retro-hint">{t("retro:saves.hint", { slot: active })}</p>
      <ul>
        {slots.map((slot) => {
          const state = progress?.states.find((s) => s.slot === slot);
          const name = slot === 0 ? t("retro:saves.auto") : t("retro:saves.slot", { slot });
          return (
            <li key={slot} className="retro-slot" data-active={slot === active || undefined}>
              <div className="retro-slot__picture">
                {state?.has_picture ? (
                  <img src={keeper.pictureUrl(slot, state.updated_at)} alt="" />
                ) : (
                  <Icon name="floppy" size={22} />
                )}
              </div>
              <div className="retro-slot__text">
                <strong>{name}</strong>
                <small>{state ? when(state.updated_at) : t("retro:saves.empty")}</small>
              </div>
              <div className="retro-slot__actions">
                {slot > 0 ? (
                  <button type="button" className="player-pill" onClick={() => onSave(slot)}>
                    {t("retro:saves.save")}
                  </button>
                ) : null}
                {state ? (
                  <button type="button" className="player-pill" onClick={() => onLoad(slot)}>
                    {t("retro:saves.load")}
                  </button>
                ) : null}
                {state && slot > 0 ? (
                  <button
                    type="button"
                    className="player-icon retro-icon"
                    onClick={() => onDelete(slot)}
                    aria-label={t("retro:saves.delete", { name })}
                  >
                    <Icon name="trash" size={18} />
                  </button>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}

export default RetroPage;
