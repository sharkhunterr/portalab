import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";
import { uiLocale } from "../../../src/i18n/format/uiLocale";

// issue 457: dates written outside useFormat() follow the interface's language, never the browser's
const SRC = resolve(dirname(fileURLToPath(import.meta.url)), "../../../src");
const files = (folder: string): string[] =>
  readdirSync(folder).flatMap((name) => {
    const path = join(folder, name);
    return statSync(path).isDirectory() ? files(path) : /\.tsx?$/.test(name) ? [path] : [];
  });

describe("dates in the interface's language", () => {
  afterEach(() => document.documentElement.removeAttribute("lang"));

  it("reads the language the provider set on the page", () => {
    document.documentElement.lang = "en";
    expect(uiLocale()).toBe("en");
    expect(new Date(Date.UTC(2026, 10, 15, 12)).toLocaleDateString(uiLocale(), { month: "long" })).toBe(
      "November",
    );
  });

  it("is never left to the browser in the interface's code", () => {
    const offenders = files(SRC).filter((path) =>
      /toLocale(Date|Time)?String\(\s*(undefined|\))/.test(readFileSync(path, "utf8")),
    );
    expect(offenders).toEqual([]);
  });
});
