import { mkdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { request } from "@playwright/test";

/**
 * Issue 469: the accounts signed in once for the whole run — one per device, each owning every product (the
 * dashboard is a member's own: the three devices' journeys run side by side without meeting), and a demo
 * member owning none (the locked side) — their sessions kept as storage states, the welcome and the guided
 * tours already seen (they would cover every page).
 */
export const OUT = process.env.NIGHTLY_OUT ?? resolve("nightly-report");
export const AUTH = resolve(OUT, ".auth");

interface Account {
  login: string;
  password: string;
}

const SEEN = {
  "shell.onboarding.welcomedAt": "2026-01-01T00:00:00Z",
  "shell.onboarding.stepsHiddenAt": "2026-01-01T00:00:00Z",
  "shell.onboarding.toursSeen": [
    "portal",
    "profile",
    "dashboard",
    "settings",
    "household",
    "news",
    "media",
    "retro",
  ],
  "shell.welcome.dismissedAt": "2026-01-01T00:00:00Z",
};

export default async function globalSetup(): Promise<void> {
  if (!process.env.NIGHTLY_STATE)
    throw new Error("NIGHTLY_STATE is not set: run backend/tests/nightly/nightly.sh");
  const state = JSON.parse(readFileSync(process.env.NIGHTLY_STATE, "utf8")) as {
    base: string;
    accounts: Record<string, Account>;
  };
  mkdirSync(AUTH, { recursive: true });
  for (const [who, account] of Object.entries(state.accounts)) {
    const context = await request.newContext({ baseURL: state.base });
    const answer = await context.post("/api/v1/auth/login", { data: account });
    if (!answer.ok()) throw new Error(`could not sign in as ${who}: ${answer.status()}`);
    const csrf = ((await answer.json()) as { csrf_token: string }).csrf_token;
    const seen = await context.put("/api/v1/me/preferences", {
      data: SEEN,
      headers: { "X-CSRF-Token": csrf },
    });
    if (!seen.ok()) throw new Error(`could not put the welcome away for ${who}: ${seen.status()}`);
    await context.storageState({ path: resolve(AUTH, `${who}.json`) });
    await context.dispose();
  }
}
