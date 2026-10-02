#!/usr/bin/env node
/**
 * Token lint (spec 022 T009/T006): components must use design tokens, never raw colors. Raw color literals
 * (#hex, rgb()/rgba(), hsl()) are allowed only in src/design-system/tokens/ and the built-in theme data.
 * Usage: node scripts/check-tokens.mjs [dir] — exits 1 and lists offenders.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

export const RAW_COLOR = /#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(/;
const ALLOWED = [
  `design-system${sep}tokens${sep}`,
  `design-system${sep}themes${sep}`,
  `api${sep}generated${sep}`,
];
const EXTENSIONS = [".ts", ".tsx", ".css"];

export function offenders(root) {
  const found = [];
  const walk = (dir) => {
    for (const name of readdirSync(dir)) {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) {
        walk(path);
        continue;
      }
      const rel = relative(root, path);
      if (!EXTENSIONS.some((ext) => name.endsWith(ext)) || ALLOWED.some((a) => rel.includes(a))) continue;
      readFileSync(path, "utf8")
        .split("\n")
        .forEach((line, index) => {
          if (RAW_COLOR.test(line) && !line.includes("token-lint-ignore")) {
            found.push(`${rel}:${index + 1}: ${line.trim()}`);
          }
        });
    }
  };
  walk(root);
  return found;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const root = process.argv[2] ?? join(fileURLToPath(new URL(".", import.meta.url)), "..", "src");
  const found = offenders(root);
  if (found.length) {
    console.error(`Raw colors outside design tokens:\n${found.join("\n")}`);
    process.exit(1);
  }
  console.log("Token lint: no raw colors outside design tokens");
}
