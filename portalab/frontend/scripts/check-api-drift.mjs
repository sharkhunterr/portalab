#!/usr/bin/env node
// CI drift check (spec 001 T058): the committed generated client must match backend/openapi.json.
// Regenerates the client into a temporary file and compares it byte-for-byte with the committed one.
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const committed = join(root, "src/api/generated/schema.ts");
const dir = mkdtempSync(join(tmpdir(), "portalab-api-"));
const fresh = join(dir, "schema.ts");

try {
  execFileSync(
    process.execPath,
    [
      join(root, "node_modules/openapi-typescript/bin/cli.js"),
      join(root, "../backend/openapi.json"),
      "-o",
      fresh,
    ],
    { stdio: "pipe" },
  );
  if (readFileSync(fresh, "utf8") !== readFileSync(committed, "utf8")) {
    console.error(
      "API client drift: run `npm run gen:api` (after `uv run portalab openapi -o openapi.json`).",
    );
    process.exit(1);
  }
  console.log("API client is in sync with backend/openapi.json");
} finally {
  rmSync(dir, { recursive: true, force: true });
}
