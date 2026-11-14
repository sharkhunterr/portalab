import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
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

import { chooseFirmware, emulatorLanguage, type Sitting } from "../../../src/features/retro/api";
import RetroPage from "../../../src/features/retro/RetroPage";
import { json } from "../../support/fake-api";

const OBJECT = "0190f0a0-0000-7000-8000-0000000000cc";
const GAME = { title: "Super Metroid", platform: "snes", core: "snes9x", threads: false, service_name: "RomM" };
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
  for (const script of document.querySelectorAll("script[src*='loader.js']")) script.remove();
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
