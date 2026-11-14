import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Issue 419 — a library's game in the portal: « Play » starts a sitting and RomM's EmulatorJS as RomM
// starts it (the core of the game's platform, its file, a verified firmware first, the emulator's French),
// the sitting kept alive while the game runs and ended when its screen time is spent; what does not play
// here says why.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import {
  chooseFirmware,
  emulatorLanguage,
  type Progress,
  type RetroRom,
  type Sitting,
} from "../../../src/features/retro/api";
import { RetroPlayButtons } from "../../../src/features/retro/Resume";
import RetroPage from "../../../src/features/retro/RetroPage";
import { json } from "../../support/fake-api";

const OBJECT = "0190f0a0-0000-7000-8000-0000000000cc";
const GAME = {
  title: "Super Metroid",
  platform: "snes",
  core: "snes9x",
  threads: false,
  service_name: "RomM",
  engine: "emulatorjs" as const,
  rom: "r1",
  roms: [] as RetroRom[],
};
const EMPTY: Progress = { sram_at: null, states: [], latest_slot: null, slots: 5 };
const rom = (id: string, variant: string | null, progress: Progress = EMPTY): RetroRom => ({
  id,
  variant,
  platform: "snes",
  core: "snes9x",
  engine: "emulatorjs" as const,
  size: 9,
  progress,
});
GAME.roms = [rom("r1", null)];
const BASE = "/api/v1/retro/sittings/0190f0a0-0000-7000-8000-0000000000dd";
const SITTING: Sitting = {
  id: "0190f0a0-0000-7000-8000-0000000000dd",
  game: GAME,
  game_url: `${BASE}/game/metroid.sfc`,
  game_name: "metroid.sfc",
  firmware: [
    { id: "4", file_name: "other.bin", verified: false, url: `${BASE}/firmware/4/other.bin` },
    { id: "5", file_name: "bios.bin", verified: true, url: `${BASE}/firmware/5/bios.bin` },
  ],
  emulator_path: "/api/v1/retro/libraries/0190f0a0-0000-7000-8000-000000000001/emulator/",
  heartbeat_s: 30,
  saves_path: `${BASE}/`,
  state_url: null,
};

const assign = vi.fn();
const sent: string[] = [];
beforeEach(() => {
  assign.mockReset();
  sent.length = 0;
  vi.stubGlobal("location", { assign, search: "", href: "http://portal.test/" });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = new Request(
        typeof input === "string" ? `http://portal.test${input}` : (input as Request),
        init,
      );
      sent.push(`${request.method} ${new URL(request.url).pathname}`);
      return fake.handler(request);
    }),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  for (const script of document.querySelectorAll("script[data-retro-loader]")) script.remove();
});

function show(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/media/${OBJECT}/play`]}>
        <Routes>
          <Route path="/media/:objectId/play" element={node} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("the emulator's settings", () => {
  it("speaks the member's language and starts with a verified firmware", () => {
    expect(emulatorLanguage("fr")).toBe("af-FR");
    expect(emulatorLanguage("de-CH")).toBe("de-GER");
    expect(emulatorLanguage("nl")).toBe("en-US");
    expect(chooseFirmware(SITTING)).toBe(`${BASE}/firmware/5/bios.bin`);
    expect(chooseFirmware({ ...SITTING, firmware: [] })).toBeNull();
  });
});

describe("a game played in the portal", () => {
  it("starts a sitting and the library's emulator, and ends it when the screen time is spent", async () => {
    let beats = 0;
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === `/api/v1/retro/games/${OBJECT}`) return json(200, GAME);
      if (path === `/api/v1/retro/games/${OBJECT}/sittings`) return json(201, SITTING);
      if (path === `${BASE}/beat`) {
        beats += 1;
        return json(200, { minutes_left: beats > 1 ? 0 : 3, stop: beats > 1 });
      }
      if (path === `${BASE}/end`) return json(204, null);
      return json(404, {});
    };
    show(<RetroPage />);
    const play = await screen.findByRole("button", { name: "Play" });
    expect(screen.getByText("SNES · RomM")).toBeTruthy();
    fireEvent.click(play);
    await waitFor(() => expect(document.querySelector("script[src*='loader.js']")).toBeTruthy());
    const script = document.querySelector<HTMLScriptElement>("script[src*='loader.js']");
    expect(script?.getAttribute("src")).toBe(`${SITTING.emulator_path}loader.js`);
    const w = window as unknown as Record<string, unknown>;
    expect([w.EJS_core, w.EJS_gameUrl, w.EJS_biosUrl, w.EJS_player, w.EJS_language]).toEqual([
      "snes9x",
      SITTING.game_url,
      `${BASE}/firmware/5/bios.bin`,
      "#retro-game",
      "en-US",
    ]);
    expect(w.EJS_disableDatabases).toBe(true);

    vi.useFakeTimers({ shouldAdvanceTime: true });
    act(() => (w.EJS_onGameStart as () => void)());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(await screen.findByText("3 minutes left")).toBeTruthy();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(await screen.findByText("Screen time is up for today. See you tomorrow!")).toBeTruthy();
    expect(sent).toContain(`POST ${BASE}/end`);
  });

  it("says why a game does not play here", async () => {
    fake.handler = () => json(404, { code: "retro.not_playable", title: "Not playable" });
    show(<RetroPage />);
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText(/no emulator here runs its console/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Back to the game's page" }));
    expect(assign).toHaveBeenCalledWith(`/media/${OBJECT}`);
  });

  it("says when a profile's screen time is spent before it starts", async () => {
    fake.handler = (request) => {
      const path = new URL(request.url).pathname;
      if (path === `/api/v1/retro/games/${OBJECT}`) return json(200, GAME);
      return json(403, { code: "household.screen_time_up", title: "Spent" });
    };
    show(<RetroPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Play" }));
    expect(await screen.findByText("Screen time is up for today. See you tomorrow!")).toBeTruthy();
  });
});

describe("saves and states (issue 420)", () => {
  const PROGRESS = {
    sram_at: "2026-11-15T09:00:00Z",
    states: [{ slot: 0, size: 8, updated_at: "2026-11-15T09:10:00Z", has_picture: false }],
    latest_slot: 0,
    slots: 5,
  };

  it("continues from the latest state, keeps a state in a slot and where the game was when leaving", async () => {
    const puts: string[] = [];
    let started: unknown = null;
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === `/api/v1/retro/games/${OBJECT}`)
        return json(200, { ...GAME, progress: PROGRESS, roms: [rom("r1", null, PROGRESS)] });
      if (path === `/api/v1/retro/games/${OBJECT}/sittings`) {
        started = await request.json();
        return json(201, { ...SITTING, state_url: `${BASE}/states/0` });
      }
      if (path === `${BASE}/saves`) return json(200, PROGRESS);
      if (request.method === "PUT") {
        puts.push(path);
        return path.endsWith("/sram") || path.endsWith("/picture")
          ? json(204, null)
          : json(200, { slot: 2, size: 5, updated_at: "2026-11-15T10:00:00Z", has_picture: false });
      }
      if (path === `${BASE}/end`) return json(204, null);
      return json(404, {});
    };
    const w = window as unknown as Record<string, unknown>;
    w.EJS_emulator = {
      pause: vi.fn(),
      takeScreenshot: async () => ({
        blob: new Blob([new Uint8Array([137, 80, 78, 71])], { type: "image/png" }),
      }),
      gameManager: {
        getState: () => new Uint8Array([1, 2, 3, 4, 5]),
        getSaveFile: () => new Uint8Array([9, 9]),
      },
    };
    show(<RetroPage />);
    expect(await screen.findByText("Which save do you resume from?")).toBeTruthy();
    const latest = screen.getByRole("button", { name: /Where you left off/ });
    expect(latest.getAttribute("aria-pressed")).toBe("true"); // the latest, chosen
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(w.EJS_loadStateURL).toBe(`${BASE}/states/0`));
    expect(started).toEqual({ resume: 0, rom: "r1" });
    act(() => (w.EJS_onGameStart as () => void)());

    fireEvent.click(await screen.findByRole("button", { name: "Saves" }));
    expect(await screen.findByText("Where you left off")).toBeTruthy();
    const slotTwo = screen.getByText("Slot 2").closest("li") as HTMLElement;
    fireEvent.click(within(slotTwo).getByRole("button", { name: "Save here" }));
    expect(await screen.findByText("Saved in slot 2")).toBeTruthy();
    expect(puts).toEqual([`${BASE}/states/2`, `${BASE}/states/2/picture`]);

    fireEvent.click(screen.getByRole("button", { name: "Quit the game" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith(`/media/${OBJECT}`));
    expect(puts).toEqual(
      expect.arrayContaining([`${BASE}/sram`, `${BASE}/states/0`, `${BASE}/states/0/picture`]),
    );
    expect(sent).toContain(`POST ${BASE}/end`);
    delete w.EJS_emulator;
  });
});

describe("engines and controls (issue 421)", () => {
  it("plays a Flash game in Ruffle, without save states", async () => {
    const flash = { ...GAME, platform: "flash", core: "ruffle", engine: "ruffle" as const };
    const path = "/api/v1/retro/libraries/0190f0a0-0000-7000-8000-000000000001/emulator/ruffle/";
    fake.handler = async (request) => {
      const at = new URL(request.url).pathname;
      if (at === `/api/v1/retro/games/${OBJECT}`) return json(200, flash);
      if (at === `/api/v1/retro/games/${OBJECT}/sittings`)
        return json(201, {
          ...SITTING,
          game: flash,
          emulator_path: path,
          game_url: `${BASE}/game/alien.swf`,
        });
      return json(404, {});
    };
    const load = vi.fn();
    show(<RetroPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Play" }));
    await waitFor(() => expect(document.querySelector("script[data-retro-loader]")).toBeTruthy());
    const script = document.querySelector<HTMLScriptElement>("script[data-retro-loader]");
    expect(script?.getAttribute("src")).toBe(`${path}ruffle.js`);
    const w = window as unknown as { RufflePlayer?: Record<string, unknown> };
    expect((w.RufflePlayer?.config as Record<string, unknown> | undefined)?.publicPath).toBe(path);
    w.RufflePlayer = {
      ...w.RufflePlayer,
      newest: () => ({ createPlayer: () => Object.assign(document.createElement("div"), { load }) }),
    };
    act(() => script?.onload?.(new Event("load")));
    expect(load).toHaveBeenCalledWith(
      expect.objectContaining({ url: `${BASE}/game/alien.swf`, publicPath: path }),
    );
    expect(screen.queryByRole("button", { name: "Saves" })).toBeNull(); // Flash keeps its own
    delete w.RufflePlayer;
  });

  it("starts with the member's controls and options, and keeps the ones changed", async () => {
    const sonic = { ...GAME, platform: "genesis", core: "genesis_plus_gx", control_scheme: "segaMD" };
    const kept: unknown[] = [];
    fake.handler = async (request) => {
      const at = new URL(request.url).pathname;
      if (at === `/api/v1/retro/games/${OBJECT}`) return json(200, sonic);
      if (at === `/api/v1/retro/games/${OBJECT}/sittings`) return json(201, { ...SITTING, game: sonic });
      if (at === "/api/v1/retro/preferences/genesis_plus_gx" && request.method === "GET")
        return json(200, {
          data: { controlSettings: { 0: { 0: { value: "x" } } }, settings: { shader: "crt" } },
        });
      if (at === "/api/v1/retro/preferences/genesis_plus_gx") {
        kept.push(await request.json());
        return json(204, null);
      }
      if (at === `${BASE}/end`) return json(204, null);
      return json(404, {});
    };
    show(<RetroPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Play" }));
    const w = window as unknown as Record<string, unknown>;
    await waitFor(() => expect(w.EJS_controlScheme).toBe("segaMD"));
    expect(w.EJS_defaultControls).toEqual({ 0: { 0: { value: "x" } } });
    expect(w.EJS_defaultOptions).toEqual({ "save-save-interval": "60", shader: "crt" });
    w.EJS_emulator = { controls: { 0: { 0: { value: "z" } } }, settings: { shader: "crt" }, gameManager: {} };
    fireEvent.click(screen.getByRole("button", { name: "Quit the game" }));
    await waitFor(() => expect(assign).toHaveBeenCalled());
    expect(kept).toEqual([
      { data: { controlSettings: { 0: { 0: { value: "z" } } }, settings: { shader: "crt" } } },
    ]);
    delete w.EJS_emulator;
    delete w.EJS_controlScheme;
  });
});

describe("loading, step by step (issue 420)", () => {
  it("shows the emulator's progress, then its error", async () => {
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === `/api/v1/retro/games/${OBJECT}`) return json(200, GAME);
      if (path === `/api/v1/retro/games/${OBJECT}/sittings`) return json(201, SITTING);
      return json(404, {});
    };
    show(<RetroPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Play" }));
    expect(await screen.findByText("Loading the emulator")).toBeTruthy();
    const steps = () =>
      Array.from(document.querySelectorAll(".retro-step")).map((li) => li.getAttribute("data-state"));
    const stage = document.getElementById("retro-game") as HTMLElement;
    const line = document.createElement("div");
    line.className = "ejs_loading_text";
    stage.appendChild(line);
    act(() => {
      line.textContent = "Download Game Core 45%";
    });
    expect(await screen.findByText("Downloading · 45 %")).toBeTruthy();
    // sitting, emulator done; the core under way; the BIOS, the game, the start to come
    await waitFor(() => expect(steps()).toEqual(["done", "done", "active", "todo", "todo", "todo"]));
    act(() => {
      line.textContent = "Download Game Data 1.50MB";
    });
    expect(await screen.findByText("Downloading · 1.5 MB")).toBeTruthy();
    await waitFor(() => expect(steps()).toEqual(["done", "done", "done", "done", "active", "todo"]));
    act(() => {
      line.className = "ejs_loading_text ejs_error_text";
      line.textContent = "Network Error";
    });
    expect(await screen.findByText("The game could not start: Network Error")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});

describe("the game's page (issue 420)", () => {
  const saved = {
    ...GAME,
    roms: [
      rom("r1", "Europe", {
        ...EMPTY,
        latest_slot: 2,
        states: [
          { slot: 0, size: 8, updated_at: "2026-11-14T20:00:00Z", has_picture: true },
          { slot: 2, size: 8, updated_at: "2026-11-14T21:00:00Z", has_picture: false },
        ],
      }),
      rom("r2", "Europe, Netherlands"),
    ],
  };

  it("always shows the saves; « Resume » asks which on the play page, a save opens the game on it", () => {
    show(<RetroPlayButtons objectId={OBJECT} game={saved} />);
    expect(screen.getByRole("link", { name: /Resume/ }).getAttribute("href")).toBe(`/media/${OBJECT}/play`);
    expect(screen.getByRole("link", { name: /New game/ }).getAttribute("href")).toBe(
      `/media/${OBJECT}/play?new=1`,
    );
    const list = screen.getByRole("list", { name: "Your saves" });
    const items = Array.from(list.querySelectorAll("button")).map((b) => b.textContent);
    expect(items).toEqual([
      expect.stringMatching(/^Slot 2.*Europe$/),
      expect.stringMatching(/^Where you left off/),
    ]);
    expect(list.querySelector("img")?.getAttribute("src")).toContain(`/states/0/picture`);
    expect(list.querySelector("img")?.getAttribute("src")).toContain("rom=r1");
    fireEvent.click(screen.getAllByRole("button", { name: /Slot 2/ })[0] as HTMLElement);
    expect(assign).toHaveBeenCalledWith(`/media/${OBJECT}/play?resume=2&rom=r1`);
  });

  it("asks which version to start for a new game when there are several", async () => {
    let body: unknown = null;
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === `/api/v1/retro/games/${OBJECT}`) return json(200, saved);
      if (path === `/api/v1/retro/games/${OBJECT}/sittings`) {
        body = await request.json();
        return json(201, SITTING);
      }
      return json(404, {});
    };
    show(<RetroPage />);
    fireEvent.click(await screen.findByRole("button", { name: "New game" }));
    expect(await screen.findByText("Which version of the game do you start?")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Europe, Netherlands/ }));
    fireEvent.click(screen.getAllByRole("button", { name: "New game" })[0] as HTMLElement);
    await waitFor(() => expect(body).toEqual({ resume: null, rom: "r2" }));
  });
});

describe("a sitting kept while the page is in the background (streaks)", () => {
  it("says when the game is not in front, and opens a new sitting when its own was closed", async () => {
    const beats: Array<[string, unknown]> = [];
    const opened: unknown[] = [];
    const SECOND = { ...SITTING, id: "0190f0a0-0000-7000-8000-0000000000ee" };
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === `/api/v1/retro/games/${OBJECT}`) return json(200, GAME);
      if (path === `/api/v1/retro/games/${OBJECT}/sittings`) {
        opened.push(await request.json());
        return json(201, opened.length === 1 ? SITTING : SECOND);
      }
      if (path.endsWith("/beat")) {
        beats.push([path, await request.json()]);
        return path.includes(SITTING.id)
          ? json(404, { code: "retro.sitting_not_found", title: "Gone" })
          : json(200, { minutes_left: null, stop: false });
      }
      return json(404, {});
    };
    show(<RetroPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Play" }));
    const w = window as unknown as Record<string, unknown>;
    await waitFor(() => expect(typeof w.EJS_onGameStart).toBe("function"));
    vi.useFakeTimers({ shouldAdvanceTime: true });
    act(() => (w.EJS_onGameStart as () => void)());
    Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "hidden" });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(beats[0]).toEqual([`/api/v1/retro/sittings/${SITTING.id}/beat`, { active: false }]);
    await waitFor(() =>
      expect(opened).toEqual([
        { resume: null, rom: "r1" },
        { resume: null, rom: "r1" },
      ]),
    );
    Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "visible" });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(beats.at(-1)).toEqual([`/api/v1/retro/sittings/${SECOND.id}/beat`, { active: true }]);
  });
});
