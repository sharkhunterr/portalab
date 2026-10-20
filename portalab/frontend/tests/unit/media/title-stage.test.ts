import { describe, expect, it } from "vitest";
import { stageOf } from "../../../src/features/media/detail/DetailPage";

// Issue 172 — a requested title's badge says the journey's stage, never the request's raw state: a film
// approved but not out yet is « Out on … », not « Downloading ».

const done = (key: string) => ({ key, status: "done" });

describe("a requested title's stage", () => {
  it("follows the first step not done", () => {
    const waiting = {
      key: "released",
      status: "waiting",
      detail: "before_cinema",
      cinema: "2027-01-13T00:00:00Z",
    };
    expect(
      stageOf({ request: { state: "processing" }, steps: [done("requested"), done("approved"), waiting] }),
    ).toEqual({
      key: "awaiting_release",
      date: "2027-01-13T00:00:00Z",
    });
    expect(stageOf({ steps: [done("requested"), { key: "approved", status: "waiting" }] })).toEqual({
      key: "pending",
    });
    expect(
      stageOf({
        steps: [
          done("requested"),
          done("approved"),
          done("released"),
          { key: "searched", status: "current" },
        ],
      }),
    ).toEqual({ key: "searching" });
    expect(
      stageOf({
        steps: [done("searched"), { key: "downloading", status: "current", items: [{ progress: 0.4 }] }],
      }),
    ).toEqual({ key: "downloading", progress: 0.4 });
    expect(stageOf({ steps: [done("downloading"), { key: "imported", status: "blocked" }] })).toEqual({
      key: "import_blocked",
    });
    expect(
      stageOf({ steps: [done("requested"), { key: "approved", status: "failed", detail: "declined" }] }),
    ).toEqual({
      key: "declined",
    });
  });

  it("never says downloading from the request's state alone", () => {
    expect(stageOf({ request: { state: "processing" } })).toEqual({ key: "searching" });
    expect(stageOf({ request: { state: "pending" } })).toEqual({ key: "pending" });
    expect(stageOf(undefined)).toBeNull();
  });
});
