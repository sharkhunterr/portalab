import { expect, type Page, test } from "@playwright/test";
import { stubApi } from "../../a11y/support";
import { element, servePack } from "./support";

// 028 T070 (US5) — a pack's booster scene dresses the opening but never decides it: over 50 openings the
// cards shown, their rarities and their order are the server's draw; a scene bringing only some parts (its
// background and its backs) leaves the others Portalab's (the faces); with less motion asked, the opening goes
// straight to the cards. The real Marée files, the API stubbed.

const RARITIES = ["common", "rare", "epic", "legendary"] as const;
const BOOSTER = {
  key: "booster_test",
  names: { en: "Test booster", fr: "Booster test" },
  descriptions: { en: "", fr: "" },
  price: 500,
  rarity: "epic",
  cards: 5,
  odds: { common: 50, rare: 32, epic: 15, legendary: 3 },
  weights: { common: 50, rare: 32, epic: 15, legendary: 3 },
  guarantee: "rare",
  refunds: { common: 10, rare: 15, epic: 20, legendary: 30 },
  pool: "looks",
  kind: "looks",
  season: null,
  packs: [],
  until: null,
  per_member: null,
  look: null,
  theme: null,
  on_sale: true,
  left: null,
  sealed: 1,
};

function card(n: number, rarity: string) {
  return {
    product: {
      key: `look_${n}`,
      type: "avatar_frame",
      name: `Look ${n}`,
      names: { en: `Look ${n}`, fr: `Look ${n}` },
      descriptions: { en: "", fr: "" },
      rarity,
      price_coins: 100,
      icon: "user",
      state: "available",
      conditions: [],
      eligibility: [],
    },
    outcome: "new",
    duplicate: false,
    refund: 0,
    locked: false,
  };
}

async function signIn(page: Page) {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 1280, height: 900 });
  await stubApi(page);
  await servePack(page, "booster-scene");
  const draws: string[][] = [];
  let seed = 7;
  const next = () => {
    seed = (seed * 1103515245 + 12345) % 2147483648;
    return seed / 2147483648;
  };
  await page.route("**/api/v1/marketplace/boosters", (route) => route.fulfill({ json: [BOOSTER] }));
  await page.route("**/api/v1/marketplace/boosters/booster_test/open**", (route) => {
    const cards = Array.from({ length: 5 }, (_, i) =>
      card(draws.length * 5 + i, RARITIES[Math.floor(next() * 4)] as string),
    );
    draws.push(cards.map((c) => `${c.product.name}:${c.product.rarity}`));
    return route.fulfill({
      json: {
        booster: BOOSTER,
        opening: { id: `o${draws.length}`, opened_at: "2026-10-16T00:00:00Z", price: 0, refund: 0 },
        cards,
      },
    });
  });
  // a partial scene: its background and its backs — the faces stay Portalab's
  await page.route("**/api/v1/visuals/scenes/booster_test", (route) =>
    route.fulfill({
      json: {
        scene: {
          pack: "maree",
          look: "maree",
          names: { en: "Tide scene" },
          parts: {
            backdrop: element("maree", "backdrop-maree", {
              type: "booster_backdrop",
              look: "maree",
              kind: "glsl",
              file: "sea.glsl",
              stage: true,
              names: { en: "The deep" },
            }),
            back: {
              common: element("maree", "back-maree", {
                type: "card_back",
                look: "maree",
                kind: "css",
                css: ["back.css"],
                names: { en: "Pearl back" },
                rarity: "common",
              }),
            },
          },
        },
      },
    }),
  );
  await page.goto("/");
  await page.getByLabel(/login/i).first().fill("alex");
  await page
    .getByLabel(/password/i)
    .first()
    .fill("correct horse battery");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("list", { name: "Dashboard" })).toBeVisible();
  return draws;
}

test("50 openings show the server's draw, dressed by a partial scene", async ({ page }) => {
  test.setTimeout(240_000);
  const draws = await signIn(page);
  for (let round = 0; round < 50; round++) {
    await page.evaluate(() =>
      window.dispatchEvent(
        new CustomEvent("portalab:booster-open", { detail: { key: "booster_test", sealed: true } }),
      ),
    );
    const stage = page.locator(".booster-stage");
    await expect(stage).toBeVisible();
    if (round === 0) {
      await expect(stage).toHaveAttribute("data-scene", "maree");
      await expect(page.locator(".booster-stage > .booster-stage__backdrop")).toHaveCount(1);
      await expect(page.locator(".booster-atmosphere")).toHaveCount(0); // the mist gave way to its background
    }
    await page.locator(".booster-stage__tear").click();
    // less motion: no tear, the cards at once — face down, they all wear the pack's common back
    await expect(page.locator(".booster-card")).toHaveCount(5);
    if (round === 0) {
      await expect(page.locator('.booster-card[data-card-back="maree"]')).toHaveCount(5);
      await expect(page.locator(".booster-card[data-rarity]")).toHaveCount(0); // nothing tells it face down
    }
    await page.getByRole("button", { name: /Reveal all/ }).click();
    await expect(page.locator('.booster-card[data-state="revealed"]')).toHaveCount(5);
    const shown = await page
      .locator(".booster-card")
      .evaluateAll((cards) =>
        cards.map(
          (c) =>
            `${c.querySelector(".booster-card__button")?.getAttribute("aria-label")?.split(" — ")[0]}:${c.getAttribute("data-rarity")}`,
        ),
      );
    expect(shown).toEqual(draws[round]);
    if (round === 0) await expect(page.locator(".booster-card[data-card-face]")).toHaveCount(0); // Portalab's faces
    await page.getByRole("button", { name: "Close" }).first().click();
    await expect(stage).toHaveCount(0);
  }
  expect(draws).toHaveLength(50);
});
