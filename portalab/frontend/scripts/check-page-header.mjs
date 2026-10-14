#!/usr/bin/env node
/**
 * Page composition lint (spec 027 T048, FR-023/FR-026, SC-007/SC-008): every page module lazily imported by
 * the router renders the design-system ``PageHeader`` (directly, through ``AdminPage`` or a component of its own folder),
 * and every ``EmptyState`` carries an ``action``. Exits 1 and lists offenders.
 */
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const SRC = join(dirname(fileURLToPath(import.meta.url)), "..", "src");
const ROUTES = join(SRC, "shell", "router", "routes.tsx");
/** Routed modules that are not pages of their own (redirects, error pages rendered by the shell). */
const EXEMPT = new Set([
  "pages/NotAvailablePage",
  "features/notifications/bell/OpenNotifications", // issue 112: opens the bell's panel over the page one came from
  "features/media/player/PlayerPage", // 027 (#2): the video player covers the whole window, no page chrome
  "features/media/reader/ReaderPage", // #21: the book reader covers the whole window, no page chrome
]);

function resolveModule(spec) {
  const base = join(dirname(ROUTES), spec);
  for (const candidate of [`${base}.tsx`, `${base}.ts`, join(base, "index.tsx")]) {
    if (existsSync(candidate)) return candidate;
  }
  return null;
}

function resolveFrom(dir, spec) {
  const base = join(dir, spec);
  for (const candidate of [`${base}.tsx`, `${base}.ts`, join(base, "index.tsx"), join(base, "index.ts")]) {
    if (existsSync(candidate)) return candidate;
  }
  return null;
}

/** The file and the relative modules it imports (or re-exports), up to ``depth`` levels. */
function closure(file, depth, seen = new Set()) {
  if (seen.has(file)) return [];
  seen.add(file);
  if (depth > 0) {
    const source = readFileSync(file, "utf8");
    for (const match of source.matchAll(/from "(\.{1,2}\/[^"]+)"/g)) {
      const target = resolveFrom(dirname(file), match[1]);
      if (target && !target.includes(`${"design-system"}`)) closure(target, depth - 1, seen);
    }
  }
  return [...seen];
}

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) walk(path, out);
    else if (/\.tsx?$/.test(name)) out.push(path);
  }
  return out;
}

export function offenders() {
  const found = [];
  const routes = readFileSync(ROUTES, "utf8");
  const specs = [...new Set([...routes.matchAll(/import\("([^"]+)"\)/g)].map((m) => m[1]))];
  for (const spec of specs) {
    const file = resolveModule(spec);
    if (!file) continue;
    const rel = relative(SRC, file).replace(/\.tsx?$/, "");
    if (EXEMPT.has(rel)) continue;
    // the page itself, or a component it imports, renders the header (route wrappers delegate to features)
    const text = closure(file, 3)
      .map((f) => readFileSync(f, "utf8"))
      .join("\n");
    // ``AdminPage`` (027 administration kit) renders the PageHeader itself
    if (!/PageHeader|<AdminPage\b/.test(text)) found.push(`${rel}: no PageHeader`);
  }
  for (const file of walk(SRC)) {
    const text = readFileSync(file, "utf8");
    for (const match of text.matchAll(/<EmptyState\b([^>]*?)\/>/gs)) {
      if (!/\baction=/.test(match[1])) found.push(`${relative(SRC, file)}: EmptyState without action`);
    }
  }
  return found;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const found = offenders();
  if (found.length) {
    process.stderr.write(`Page composition lint: ${found.length} offender(s)\n${found.join("\n")}\n`);
    process.exit(1);
  }
  process.stdout.write("Page composition lint: every routed page has a PageHeader\n");
}
