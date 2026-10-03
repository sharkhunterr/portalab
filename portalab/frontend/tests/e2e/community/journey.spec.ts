import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";
import { stubApi } from "../../a11y/support";

// 012 T028 — propose → vote → participate → recognize, keyboard only; the lifecycle section degrades alone
// when Marketplace is stopped; the page fits a phone. No follow/friend/message/like control anywhere.

const ME = "00000000-0000-7000-8000-000000000001";
const SAM = "00000000-0000-7000-8000-000000000002";
const PERMISSIONS = [
  "users.self.manage",
  "community.read",
  "community.propose",
  "community.participate",
  "marketplace.read",
];

async function signIn(page: Page) {
  await page.goto("/");
  await page.getByLabel(/login/i).first().fill("alex");
  await page
    .getByLabel(/password/i)
    .first()
    .fill("correct horse battery");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: /Search/ })).toBeVisible();
}

async function stubCommunity(page: Page) {
  const proposals: Array<Record<string, unknown>> = [];
  const participations: Array<Record<string, unknown>> = [];
  const json = (body: unknown, status = 200) => ({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
  await page.route("**/api/v1/me/permissions", (route) =>
    route.fulfill(json({ permissions: PERMISSIONS, roles: ["user"] })),
  );
  await page.route("**/api/v1/community/proposals**", async (route) => {
    const url = new URL(route.request().url());
    const method = route.request().method();
    const parts = url.pathname.split("/").slice(4); // ["proposals", id?, action?, ...]
    const proposal = proposals.find((p) => p.id === parts[1]);
    if (parts.length === 1 && method === "POST") {
      const body = route.request().postDataJSON() as { title: string; kind: string };
      const created = {
        id: `00000000-0000-7000-8000-0000000001${proposals.length}0`,
        kind: body.kind,
        title: body.title,
        body_md: "",
        rendered_html: "<p>Let us build it.</p>",
        tags: [],
        status: "open",
        help_wanted: false,
        help_note: null,
        proposer: { id: ME, display_name: "Alex" },
        mine: true,
        votes: 0,
        my_vote: false,
        lifecycle: { state: "unavailable" },
        created_at: "2026-10-01T12:00:00Z",
      };
      proposals.push(created);
      participations.push({
        id: "p-sam",
        role: "tester",
        note: null,
        member: { id: SAM, display_name: "Sam" },
        mine: false,
        recognized: false,
      });
      return route.fulfill(json(created, 201));
    }
    if (parts.length === 1)
      return route.fulfill(json(url.searchParams.get("mine") === "true" ? proposals : proposals));
    if (!proposal)
      return route.fulfill(
        json({ code: "community.proposal_not_found", title: "Not found", status: 404 }, 404),
      );
    if (parts[2] === "vote") {
      proposal.my_vote = method === "POST";
      proposal.votes = method === "POST" ? 1 : 0;
      return route.fulfill(json({ votes: proposal.votes, my_vote: proposal.my_vote }));
    }
    if (parts[2] === "participations" && parts[4] === "recognize") {
      const row = participations.find((p) => p.id === parts[3]);
      if (row) row.recognized = true;
      return route.fulfill(json({ ...row, recognized: true }));
    }
    if (parts[2] === "participations") return route.fulfill(json(participations));
    if (parts[2] === "participation" && method === "POST") {
      const row = {
        id: "p-me",
        role: "contributor",
        note: null,
        member: { id: ME, display_name: "Alex" },
        mine: true,
        recognized: false,
      };
      participations.push(row);
      return route.fulfill(json(row, 201));
    }
    return route.fulfill(json(proposal));
  });
}

async function press(page: Page, name: string | RegExp) {
  const target = page.getByRole("button", { name });
  await target.focus();
  await page.keyboard.press("Enter");
}

test("propose, vote, participate and recognize — keyboard only", async ({ page }) => {
  await stubApi(page);
  await stubCommunity(page);
  await signIn(page);
  await page.goto("/community/proposals");
  await expect(page.getByRole("heading", { name: "Open proposals" })).toBeVisible();
  await page.getByLabel("Title").focus();
  await page.keyboard.type("Dark mode");
  await press(page, "Submit the proposal");
  await expect(page.getByRole("status").filter({ hasText: "Your proposal is published." })).toBeVisible();
  const link = page.getByRole("link", { name: "Dark mode" }).first();
  await link.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { level: 1, name: "Dark mode" })).toBeVisible();

  await press(page, "Support");
  await expect(page.getByText("1 supporter")).toBeVisible();
  await expect(page.getByRole("button", { name: "Withdraw my support" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.getByText("The project's progress is temporarily unavailable.")).toBeVisible();

  await press(page, "Take part");
  await expect(page.getByRole("button", { name: "Stop taking part" })).toBeVisible();
  await press(page, "Recognize this contribution");
  await expect(page.getByText(/Sam · Tester · recognized/)).toBeVisible();

  for (const name of [/follow/i, /friend/i, /message/i, /like/i]) {
    await expect(page.getByRole("button", { name })).toHaveCount(0);
  }
  const results = await new AxeBuilder({ page }).include("main").analyze();
  expect(results.violations).toEqual([]);
});

test("proposals on a phone", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 });
  await stubApi(page);
  await stubCommunity(page);
  await signIn(page);
  await page.goto("/community/proposals");
  await expect(page.getByRole("heading", { name: "Open proposals" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(overflow).toBe(false);
});
