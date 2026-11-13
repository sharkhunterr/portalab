// Issue 404 — what a first visit downloads stays within budget: the entry chunk and every chunk it imports
// statically (what the browser fetches before the page shows), gzip-compressed. Run after `npm run build`.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { gzipSync } from "node:zlib";

const BUDGET_KB = Number(process.env.BUNDLE_BUDGET_KB ?? 600);
const dist = new URL("../dist/", import.meta.url).pathname;
const html = readFileSync(join(dist, "index.html"), "utf8");
const pending = [...html.matchAll(/(?:src|href)="\/assets\/([^"]+\.js)"/g)].map((m) => m[1]);
const seen = new Set();
while (pending.length) {
  const file = pending.pop();
  if (seen.has(file)) continue;
  seen.add(file);
  const code = readFileSync(join(dist, "assets", file), "utf8");
  for (const m of code.matchAll(/(?:import|from)\s*["']\.\/([^"']+\.js)["']/g)) pending.push(m[1]);
}
const sizes = [...seen].map((file) => [file, gzipSync(readFileSync(join(dist, "assets", file))).length]);
const total = sizes.reduce((sum, [, size]) => sum + size, 0) / 1024;
for (const [file, size] of sizes.sort((a, b) => b[1] - a[1]))
  console.log(`${(size / 1024).toFixed(0).padStart(6)} KB gz  ${file}`);
console.log(`first visit: ${total.toFixed(0)} KB gz (budget ${BUDGET_KB} KB)`);
if (total > BUDGET_KB) {
  console.error(
    "over budget: load the new code lazily (a route, a dialog) or keep it out of the vendor chunk",
  );
  process.exit(1);
}
