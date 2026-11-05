import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Issue 354: the team's technical sheet of a ticket's media — asked of the services only once opened.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { MediaSheet } from "../../src/features/support/tickets/MediaSheet";
import { json } from "../support/fake-api";

const stream = (kind: string, extra: Record<string, unknown>) => ({
  kind,
  codec: null,
  language: null,
  title: null,
  channels: null,
  resolution: null,
  dynamic_range: null,
  bitrate: null,
  forced: false,
  default: false,
  ...extra,
});

const SHEET = {
  servers: [
    {
      service: "Plex",
      added_at: "2026-10-06T01:38:57Z",
      files: [
        {
          path: "/movies/Spider-Man.mkv",
          size: 20_000_000_000,
          container: "mkv",
          duration_s: 9000,
          bitrate: 18500,
          streams: [
            stream("video", { codec: "hevc", resolution: "2160p", dynamic_range: "Dolby Vision" }),
            stream("audio", { codec: "eac3", language: "Français", channels: "5.1", default: true }),
            stream("audio", { codec: "truehd", language: "English", channels: "7.1" }),
            stream("subtitle", { codec: "srt", language: "Français", forced: true }),
          ],
        },
      ],
    },
  ],
  acquisition: {
    service: "Radarr",
    added_at: "2026-10-05T05:17:57Z",
    quality: "WEBDL-2160p",
    size: 20_000_000_000,
    files: 1,
    expected: 1,
    link: null,
    events: [
      {
        event: "grabbed",
        at: "2026-10-05T05:20:00Z",
        release: "Spider-Man.Brand.New.Day.2026.MULTi.2160p.WEB-GRP",
        indexer: "Ygg",
        client: "Deluge",
        download_id: "ABCDEF0123",
      },
    ],
  },
};

describe("a ticket's media technical sheet", () => {
  it("asks the services once opened and shows the file, its streams and the torrent", async () => {
    const asked: string[] = [];
    fake.handler = (request) => {
      asked.push(new URL(request.url).pathname);
      return json(200, SHEET);
    };
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(
      <QueryClientProvider client={client}>
        <MediaSheet ticketId="t-1" />
      </QueryClientProvider>,
    );
    expect(asked).toEqual([]); // folded: nothing asked
    const details = container.querySelector("details") as HTMLDetailsElement;
    details.open = true;
    fireEvent(details, new Event("toggle"));
    expect(await screen.findByText("/movies/Spider-Man.mkv")).toBeTruthy();
    expect(asked).toEqual(["/api/v1/tickets/t-1/media-sheet"]);
    expect(screen.getByText(/2160p · HEVC · Dolby Vision/)).toBeTruthy();
    expect(screen.getByText("Audio (2 tracks)")).toBeTruthy();
    expect(screen.getByText(/English · TRUEHD · 7\.1/)).toBeTruthy();
    expect(screen.getByText("forced")).toBeTruthy();
    expect(screen.getByText("Spider-Man.Brand.New.Day.2026.MULTi.2160p.WEB-GRP")).toBeTruthy();
    expect(screen.getByText("ABCDEF0123")).toBeTruthy();
    expect(screen.getByText(/indexer Ygg · client Deluge/)).toBeTruthy();
  });
});
