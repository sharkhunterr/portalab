import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { beforeAll, describe, expect, it, vi } from "vitest";

// 027 (#11) — casting: in a Chromium browser the Cast SDK loads, a cast button shows when a device is
// around; once connected, the local stream stops, a remote stream starts (subtitles burnt in for the TV)
// and the TV is given its remote playlist at the current position; the page then shows « Playing on … ».

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});
vi.mock("hls.js", () => {
  class FakeHls {
    static isSupported() {
      return true;
    }
    static Events = { ERROR: "hlsError", MANIFEST_PARSED: "hlsManifestParsed" };
    static ErrorTypes = { MEDIA_ERROR: "mediaError" };
    on() {}
    loadSource() {}
    attachMedia() {}
    destroy() {}
  }
  return { default: FakeHls };
});

import { PlayerPage } from "../../../src/features/media/player/PlayerPage";
import { json } from "../../support/fake-api";
import { INFO } from "./player-fixtures";

const ID = "0190f0a0-0000-7000-8000-0000000000cc";
const listeners: Record<string, Array<() => void>> = {};
const loaded: Array<Record<string, unknown>> = [];
const remote = {
  isConnected: false,
  isPaused: false,
  currentTime: 0,
  duration: 7000,
  volumeLevel: 1,
  isMuted: false,
  playerState: null as string | null,
};
let requested = 0;

function fakeSdk() {
  const session = {
    getCastDevice: () => ({ friendlyName: "Salon" }),
    loadMedia: async (request: Record<string, unknown>) => {
      loaded.push(request);
    },
  };
  const context = {
    setOptions() {},
    getCastState: () => "NOT_CONNECTED",
    getCurrentSession: () => (remote.isConnected ? session : null),
    requestSession: async () => {
      requested += 1;
    },
    endCurrentSession() {},
    addEventListener(type: string, handler: () => void) {
      listeners[type] = [...(listeners[type] ?? []), handler];
    },
    removeEventListener() {},
  };
  const w = window as unknown as Record<string, unknown>;
  w.cast = {
    framework: {
      CastContext: { getInstance: () => context },
      CastContextEventType: { CAST_STATE_CHANGED: "caststate", SESSION_STATE_CHANGED: "sessionstate" },
      CastState: { NO_DEVICES_AVAILABLE: "NO_DEVICES_AVAILABLE" },
      SessionState: {},
      RemotePlayer: class {
        constructor() {
          // biome-ignore lint/correctness/noConstructorReturn: the shared fake player
          return remote;
        }
      },
      RemotePlayerController: class {
        addEventListener(type: string, handler: () => void) {
          listeners[type] = [...(listeners[type] ?? []), handler];
        }
        removeEventListener() {}
        playOrPause() {}
        seek() {}
        setVolumeLevel() {}
        muteOrUnmute() {}
      },
      RemotePlayerEventType: { ANY_CHANGE: "anychange" },
    },
  };
  w.chrome = {
    cast: {
      media: {
        DEFAULT_MEDIA_RECEIVER_APP_ID: "CC1AD845",
        MediaInfo: class {
          contentId: string;
          contentType: string;
          constructor(url: string, type: string) {
            this.contentId = url;
            this.contentType = type;
          }
        },
        MovieMetadata: class {},
        LoadRequest: class {
          media: unknown;
          constructor(media: unknown) {
            this.media = media;
          }
        },
        StreamType: { BUFFERED: "BUFFERED" },
      },
      AutoJoinPolicy: { ORIGIN_SCOPED: "origin_scoped" },
    },
  };
}

beforeAll(() => {
  Object.defineProperty(HTMLMediaElement.prototype, "play", {
    configurable: true,
    value: () => Promise.resolve(),
  });
  Object.defineProperty(HTMLMediaElement.prototype, "pause", { configurable: true, value: () => undefined });
  Object.defineProperty(HTMLMediaElement.prototype, "load", { configurable: true, value: () => undefined });
  Object.defineProperty(navigator, "userAgent", {
    configurable: true,
    value: "Mozilla/5.0 Chrome/130.0 Safari/537.36",
  });
  const append = document.head.appendChild.bind(document.head);
  document.head.appendChild = (<T extends Node>(node: T): T => {
    if (node instanceof HTMLScriptElement && node.src.includes("cast_sender.js")) {
      fakeSdk();
      queueMicrotask(() =>
        (window as unknown as { __onGCastApiAvailable: (ok: boolean) => void }).__onGCastApiAvailable(true),
      );
      return node;
    }
    return append(node);
  }) as typeof document.head.appendChild;
});

function fire(type: string) {
  for (const handler of listeners[type] ?? []) handler();
}

describe("casting", () => {
  it("hands the stream to the TV with its remote playlist", async () => {
    const starts: Array<Record<string, unknown>> = [];
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path.endsWith("/player"))
        return json(200, { ...INFO, item: { ...INFO.item, resume_s: 0 }, cast_base_url: null });
      if (path.endsWith("/player/start")) {
        const body = (await request.json()) as Record<string, unknown>;
        starts.push(body);
        const n = starts.length;
        return json(200, {
          ticket: `${"t".repeat(40)}${n}.${"m".repeat(24)}`,
          playlist: `session/s${n}/base/index.m3u8`,
          remote_playlist: body.remote
            ? `/api/v1/media/remote/${"r".repeat(40)}.${"k".repeat(24)}/session/s${n}/base/index.m3u8`
            : null,
          video: "copy",
          audio: "transcode",
          subtitles: body.burn ? "burn" : "text",
          width: 1920,
          height: 800,
          bitrate_kbps: 5800,
          video_codec: "h264",
          audio_codec: "aac",
        });
      }
      if (path.endsWith("/subtitles")) return json(200, { cues: [] });
      return new Response(null, { status: 204 });
    };
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const router = createMemoryRouter([{ path: "/media/:objectId/watch", element: <PlayerPage /> }], {
      initialEntries: [`/media/${ID}/watch`],
    });
    render(
      <QueryClientProvider client={client}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(starts).toHaveLength(1));
    expect(starts[0]).toMatchObject({ remote: false, burn: false, subtitle: "s1" });

    const castButton = await screen.findByRole("button", { name: "Cast to a device" });
    fireEvent.click(castButton);
    expect(requested).toBe(1);

    remote.isConnected = true;
    remote.currentTime = 0;
    await act(async () => fire("anychange"));
    await waitFor(() => expect(starts).toHaveLength(2));
    expect(starts[1]).toMatchObject({ remote: true, burn: true, subtitle: "s1" }); // the TV cannot draw them
    await waitFor(() => expect(loaded).toHaveLength(1));
    const media = loaded[0]?.media as { contentId: string; contentType: string };
    expect(media.contentId).toMatch(
      /^http:\/\/[^/]+\/api\/v1\/media\/remote\/r+\.k+\/session\/s2\/base\/index\.m3u8$/,
    );
    expect(media.contentType).toBe("application/x-mpegURL");
    expect(await screen.findByText("Playing on Salon")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "Stop casting" }).length).toBeGreaterThan(0);
  });
});
