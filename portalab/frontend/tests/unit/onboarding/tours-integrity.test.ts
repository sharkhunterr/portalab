import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { matchRoutes } from "react-router";
import { describe, expect, it } from "vitest";
import { TOURS } from "../../../src/features/onboarding/tours";
import { routes } from "../../../src/shell/router/routes";

// issue 459: each guided tour still works with the interface it walks through — checked at every pipeline,
// so at every release. The end-to-end walk is tests/e2e/onboarding/tours.spec.ts.
const here = dirname(fileURLToPath(import.meta.url));
const SRC = resolve(here, "../../../src");
const BACKEND = resolve(here, "../../../../backend");

function sources(folder: string): string[] {
  return readdirSync(folder).flatMap((name) => {
    const path = join(folder, name);
    if (statSync(path).isDirectory()) return name === "generated" ? [] : sources(path);
    return /\.(tsx?|css)$/.test(name) && !path.endsWith("onboarding/tours.ts") ? [path] : [];
  });
}
const CODE = sources(SRC)
  .map((path) => readFileSync(path, "utf8"))
  .join("\n");
const catalog = (language: string) =>
  JSON.parse(readFileSync(join(BACKEND, "locales", language, "onboarding.json"), "utf8")) as Record<
    string,
    string
  >;

/** What a selector needs from the code: its classes, ``data-tour`` names and ids. */
function needs(selector: string): string[] {
  const missing: string[] = [];
  for (const [, name] of selector.matchAll(/\.([A-Za-z][\w-]*)/g))
    if (!new RegExp(`(?<![\\w-])${name}(?![\\w-])`).test(CODE)) missing.push(`.${name}`);
  for (const [, name] of selector.matchAll(/data-tour='([^']+)'/g))
    if (!new RegExp(`data-tour=\\{?["'\`]${name}["'\`]`).test(CODE)) missing.push(`[data-tour='${name}']`);
  for (const [, name] of selector.matchAll(/#([\w-]+)/g))
    if (!CODE.includes(name as string)) missing.push(`#${name}`);
  return missing;
}

describe("the guided tours", () => {
  it.each(["en", "fr"])("have their words in %s for every step", (language) => {
    const words = catalog(language);
    const missing = TOURS.flatMap((tour) => [
      ...["title", "description"].map((k) => `tours.${tour.key}.${k}`),
      ...tour.steps.flatMap((step) => ["title", "text"].map((k) => `tours.${tour.key}.${step.key}.${k}`)),
    ]).filter((key) => !words[key]);
    expect(missing).toEqual([]);
  });

  it("light elements the interface still draws (each step has a target present in the code)", () => {
    const dead = TOURS.flatMap((tour) =>
      tour.steps
        .filter((step) => step.targets.length > 0 && step.targets.every((target) => needs(target).length > 0))
        .map((step) => `${tour.key}.${step.key}: ${step.targets.join(" | ")}`),
    );
    expect(dead).toEqual([]);
  });

  it("open pages the portal has", () => {
    const table = routes(null);
    const unknown = TOURS.flatMap((tour) =>
      [tour.route, ...tour.steps.flatMap((step) => (step.route ? [step.route] : []))]
        .map((route) => route.split("?")[0] as string)
        .filter((route) => {
          const found = matchRoutes(table, route);
          return !found || found.at(-1)?.route.path === "*";
        })
        .map((route) => `${tour.key}: ${route}`),
    );
    expect(unknown).toEqual([]);
  });

  it("lead to first-steps missions the portal defines", () => {
    const discovery = readFileSync(
      join(BACKEND, "src/portalab/modules/gamification/quests/discovery.py"),
      "utf8",
    );
    const missions = TOURS.flatMap((tour) => (tour.mission ? [tour.mission] : []));
    expect(missions.filter((mission) => !discovery.includes(`"${mission}"`))).toEqual([]);
  });

  it("are each named once, and each step once in its tour", () => {
    const keys = TOURS.map((tour) => tour.key);
    expect(new Set(keys).size).toBe(keys.length);
    for (const tour of TOURS) {
      const steps = tour.steps.map((step) => step.key);
      expect(new Set(steps).size, tour.key).toBe(steps.length);
      expect(tour.steps.at(-1)?.targets, tour.key).toEqual([]);
    }
  });
});
