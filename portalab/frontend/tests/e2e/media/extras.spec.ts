import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { stubTourPortal } from "../onboarding/fixtures";
import { expectNoOverflow, signIn } from "../support/portal";

// Issue 465 — a title's videos and pictures on its page, on a phone and on a desktop: within the screen, the
// pictures opening a viewer that turns them and gives the focus back; YouTube loaded only once asked.

const MOVIE = "00000000-0000-7000-8000-0000000000a1"; // the stubbed library's « The Long Night »
const BASE = `/api/v1/media/${MOVIE}/extras`;
// a 1×1 JPEG
const PIXEL = Buffer.from(
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q==",
  "base64",
);
const EXTRAS = {
  videos: [
    ["abcdefghijk", "Official trailer", "trailer"],
    ["bcdefghijkl", "Teaser", "teaser"],
    ["cdefghijklm", "The making of a long night", "behind_the_scenes"],
  ].map(([youtube, name, kind], index) => ({
    index,
    site: "youtube",
    youtube,
    play: null,
    name,
    kind,
    language: "en",
    duration_s: 95,
    picture: `${BASE}/videos/${index}/picture`,
  })),
  images: Array.from({ length: 6 }, (_, index) => ({
    index,
    kind: index < 4 ? "backdrop" : "still",
    preview: `${BASE}/images/${index}?preview=true`,
    full: `${BASE}/images/${index}`,
  })),
};

for (const [width, viewport] of Object.entries({
  phone: { width: 390, height: 844 },
  desktop: { width: 1280, height: 900 },
})) {
  test(`a title's videos and pictures at ${width} width`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await stubTourPortal(page);
    const youtube: string[] = [];
    await page.route(/youtube(-nocookie)?\.com/, (route) => {
      youtube.push(route.request().url());
      return route.abort();
    });
    await page.route(`**${BASE}**`, (route) => {
      const path = new URL(route.request().url()).pathname;
      return path === BASE
        ? route.fulfill({ json: EXTRAS })
        : route.fulfill({ body: PIXEL, contentType: "image/jpeg" });
    });
    await signIn(page);
    await page.goto(`/media/${MOVIE}`);

    const videos = page.getByRole("list", { name: "Videos" });
    await expect(videos.getByRole("listitem")).toHaveCount(3);
    await expect(page.getByRole("list", { name: "Pictures" }).getByRole("listitem")).toHaveCount(6);
    await expectNoOverflow(page, `extras@${width}`);
    expect(youtube).toEqual([]); // nothing asked of YouTube before a video is played
    const section = await new AxeBuilder({ page }).include(".media-extras").analyze();
    expect(section.violations.map((v) => v.id)).toEqual([]);

    // the viewer: over the whole screen, turned, closed — the focus back on the picture opened
    const opener = page.getByRole("button", { name: "Open picture 2 of 6" });
    await opener.click();
    const viewer = page.getByRole("dialog", { name: "Pictures of The Long Night" });
    await expect(viewer).toBeVisible();
    const box = await viewer.boundingBox();
    expect(box?.width).toBe(viewport.width);
    await viewer.getByRole("button", { name: "Next picture" }).click();
    await expect(viewer.getByText("3 / 6")).toBeVisible();
    const inViewer = await new AxeBuilder({ page }).include(".extras-viewer").analyze();
    expect(inViewer.violations.map((v) => v.id)).toEqual([]);
    await page.keyboard.press("ArrowLeft");
    await expect(viewer.getByText("2 / 6")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(viewer).toHaveCount(0);
    await expect(opener).toBeFocused();

    // reached by an IP address, YouTube would refuse to play here: the video opens on YouTube
    await expect(videos.getByRole("link", { name: /“Official trailer” on YouTube/ })).toHaveAttribute(
      "href",
      "https://www.youtube.com/watch?v=abcdefghijk",
    );
    // reached by a name, YouTube's privacy-enhanced player plays it here, once asked
    await page.goto(`http://localhost:5199/media/${MOVIE}`);
    await videos.getByRole("button", { name: "Play “Official trailer”" }).click();
    const player = page.getByRole("dialog", { name: "Official trailer" });
    await expect(player.locator("iframe")).toHaveAttribute(
      "src",
      /^https:\/\/www\.youtube-nocookie\.com\/embed\/abcdefghijk\?/,
    );
    await expectNoOverflow(page, `extras-player@${width}`);
  });
}
