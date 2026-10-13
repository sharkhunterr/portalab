import { describe, expect, it } from "vitest";
import { readingColors } from "../../src/design-system/themes/reading";
import { audioUrl, clock, fileUrl, pageUrl } from "../../src/features/media/books/api";

/** #20, #21: listening and reading in the portal — times, the relayed addresses, the page colours. */
describe("books", () => {
  it("shows times like a player", () => {
    expect(clock(0)).toBe("0:00");
    expect(clock(65.9)).toBe("1:05");
    expect(clock(3 * 3600 + 7 * 60 + 2)).toBe("3:07:02");
    expect(clock(-4)).toBe("0:00");
  });

  it("addresses everything through the portal, under the ticket", () => {
    expect(audioUrl("T.k", null)).toBe("/api/v1/media/listen/T.k/audio");
    expect(audioUrl("T.k", 3)).toBe("/api/v1/media/listen/T.k/audio?track=3");
    expect(fileUrl("T.k", "12.epub")).toBe("/api/v1/media/read/T.k/file/12.epub");
    expect(pageUrl("T.k", "12.cbx", 4)).toBe("/api/v1/media/read/T.k/page/12.cbx/4");
  });

  it("gives the pages their reading colours, following the theme when asked", () => {
    expect(readingColors("sepia").background).not.toBe(readingColors("dark").background);
    document.documentElement.dataset.colorScheme = "light";
    expect(readingColors("auto")).toEqual(readingColors("light"));
    document.documentElement.dataset.colorScheme = "dark";
    expect(readingColors("auto")).toEqual(readingColors("dark"));
  });
});
