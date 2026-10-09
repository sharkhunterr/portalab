import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

// 027 (#2) — the portal's player: a resume point is offered, the stream starts with the remembered quality
// and the member's subtitle, hls.js reads the relayed playlist from the right position, a quality picked in
// the settings restarts the stream there (the old one stopped), text subtitles are drawn from the cues,
// and a member with no linked account is sent to link it.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

const hls = vi.hoisted(() => ({
  instances: [] as Array<{ config: Record<string, unknown>; source?: string }>,
}));
vi.mock("hls.js", () => {
  class FakeHls {
    static isSupported() {
      return true;
    }
    static Events = { ERROR: "hlsError", MANIFEST_PARSED: "hlsManifestParsed" };
    static ErrorTypes = { MEDIA_ERROR: "mediaError" };
    config: Record<string, unknown>;
    source?: string;
    constructor(config: Record<string, unknown>) {
      this.config = config;
      hls.instances.push(this);
    }
    on() {}
    loadSource(url: string) {
      this.source = url;
    }
    attachMedia() {}
    destroy() {}
    recoverMediaError() {}
  }
  return { default: FakeHls };
});

import { PlayerPage } from "../../../src/features/media/player/PlayerPage";
import { clock, qualitiesFor } from "../../../src/features/media/player/quality";
import { json } from "../../support/fake-api";
import { INFO, VERSION } from "./player-fixtures";

const ID = "0190f0a0-0000-7000-8000-0000000000bb";
const TICKET = `${"a".repeat(40)}.${"b".repeat(24)}`;
beforeAll(() => {
  Object.defineProperty(HTMLMediaElement.prototype, "play", {
    configurable: true,
    value: () => Promise.resolve(),
  });
  Object.defineProperty(HTMLMediaElement.prototype, "pause", { configurable: true, value: () => undefined });
  Object.defineProperty(HTMLMediaElement.prototype, "load", { configurable: true, value: () => undefined });
});

afterEach(() => {
  hls.instances.length = 0;
  localStorage.clear();
});

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(
    [
      { path: "/media/:objectId/watch", element: <PlayerPage /> },
      { path: "/media/:objectId", element: <p>Title page</p> },
      { path: "/settings/media-accounts", element: <p>Accounts</p> },
    ],
    { initialEntries: [`/media/${ID}/watch`] },
  );
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("player helpers", () => {
  it("offers only the qualities below the file's bitrate, and formats times", () => {
    expect(qualitiesFor(INFO.qualities, VERSION)).toEqual([
      "original",
      "4m",
      "3m",
      "2m",
      "1500k",
      "720k",
      "320k",
    ]);
    expect(clock(3723)).toBe("1:02:03");
    expect(clock(65)).toBe("1:05");
  });
});

describe("player", () => {
  it("resumes, starts the stream, restarts it at another quality and draws the subtitles", async () => {
    const starts: Array<Record<string, unknown>> = [];
    const posts: string[] = [];
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path.endsWith("/player")) return json(200, INFO);
      if (path.endsWith("/player/start")) {
        starts.push((await request.json()) as Record<string, unknown>);
        return json(200, {
          ticket: `${TICKET}${starts.length}`.slice(0, 41) + TICKET.slice(41),
          playlist: `session/s${starts.length}/base/index.m3u8`,
          video: "copy",
          audio: "transcode",
          subtitles: "text",
          width: 1920,
          height: 800,
          bitrate_kbps: 5800,
          video_codec: "h264",
          audio_codec: "aac",
        });
      }
      if (path.endsWith("/subtitles"))
        return json(200, { cues: [{ start_s: 1234, end_s: 1240, text: "Mother?" }] });
      if (request.method === "POST") {
        posts.push(path.split("/").slice(-1)[0] ?? "");
        return new Response(null, { status: 204 });
      }
      return json(404, {});
    };
    localStorage.setItem("portalab.player", JSON.stringify({ quality: "8m" })); // too high for this file
    show();

    fireEvent.click(await screen.findByRole("button", { name: /20:34/ })); // resume at 20:34
    await waitFor(() => expect(starts).toHaveLength(1));
    expect(starts[0]).toMatchObject({ item: "100", quality: "original", subtitle: "s1", audio: "a1" });
    await waitFor(() => expect(hls.instances).toHaveLength(1));
    expect(hls.instances[0]?.config.startPosition).toBe(1234);
    expect(hls.instances[0]?.source).toMatch(
      /^\/api\/v1\/media\/player\/.+\/session\/s1\/base\/index\.m3u8$/,
    );

    const video = document.querySelector("video") as HTMLVideoElement;
    Object.defineProperty(video, "currentTime", { configurable: true, writable: true, value: 1235 });
    await act(async () => {
      video.dispatchEvent(new Event("timeupdate"));
    });
    expect(await screen.findByText("Mother?")).toBeTruthy();

    // the chapters: the one under the pointer, named (or numbered) with its picture
    const bar = document.querySelector(".player-bar") as HTMLElement;
    bar.getBoundingClientRect = () => ({ left: 0, width: 1000, top: 0, height: 10 }) as DOMRect;
    expect(document.querySelectorAll('.player-mark[data-kind="chapter"]')).toHaveLength(1);
    fireEvent.pointerMove(bar, { clientX: 200 });
    expect(await screen.findByText("Chapter 1")).toBeTruthy();
    expect(document.querySelector(".player-hover img")?.getAttribute("src")).toMatch(
      /image\?ref=chapter%3A7%3A1$/,
    );
    fireEvent.pointerMove(bar, { clientX: 600 });
    expect(await screen.findByText("Finale")).toBeTruthy();
    expect(document.querySelector(".player-hover img")).toBeNull();
    fireEvent.pointerLeave(bar);

    fireEvent.click(screen.getByRole("button", { name: "Playback settings" }));
    fireEvent.click(await screen.findByRole("button", { name: /Quality/ }));
    fireEvent.click(await screen.findByRole("button", { name: /4 Mb\/s · 720p/ }));
    await waitFor(() => expect(starts).toHaveLength(2));
    expect(starts[1]).toMatchObject({ quality: "4m" });
    await waitFor(() => expect(hls.instances[1]?.config.startPosition).toBe(1235)); // where it was
    await waitFor(() => expect(posts).toContain("stop")); // the first stream is let go
    expect(JSON.parse(localStorage.getItem("portalab.player") ?? "{}").quality).toBe("4m");
  });

  it("asks a member with no linked account to link it", async () => {
    fake.handler = () => json(409, { code: "media.player_unlinked", title: "Link your account" });
    show();
    const link = await screen.findByRole("link", { name: /Link my account/ });
    fireEvent.click(link);
    expect(await screen.findByText("Accounts")).toBeTruthy();
  });
});
